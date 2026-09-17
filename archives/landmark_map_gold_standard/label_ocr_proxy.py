#!/usr/bin/env python3
"""Optional SpaceXAI vision sidecar for map-label reading and image search.

  export XAI_API_KEY=...
  python3 label_ocr_proxy.py

The digitizer calls:
  POST http://127.0.0.1:8765/read-label   — identify a crop
  POST http://127.0.0.1:8765/find-text    — locate a query string in an image
  GET  http://127.0.0.1:8765/health

The API key never goes in the HTML file.
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "127.0.0.1"
PORT = 8765
MODEL = os.environ.get("XAI_MODEL", "grok-4.5")
API = "https://api.x.ai/v1/responses"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("[%s] " % self.log_date_time_string() + (fmt % args))

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path.rstrip("/") == "/health":
            key = bool(os.environ.get("XAI_API_KEY"))
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps({"ok": True, "has_key": key, "model": MODEL}).encode()
            )
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        path = self.path.rstrip("/")
        key = os.environ.get("XAI_API_KEY")
        if not key:
            self._json(500, {"error": "XAI_API_KEY is not set"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            self._json(400, {"error": "invalid JSON"})
            return
        image_url = body.get("image_url") or body.get("data_url")
        if not image_url:
            self._json(400, {"error": "missing image_url"})
            return
        if path == "/read-label":
            self._read_label(key, image_url, body.get("lexicon") or [])
            return
        if path == "/find-text":
            self._find_text(key, image_url, str(body.get("query") or "").strip())
            return
        self.send_response(404)
        self.end_headers()

    def _read_label(self, key, image_url, lexicon):
        lex = ", ".join(str(x) for x in lexicon[:200])
        prompt = (
            "This is a tiny crop from a hand-drawn 1939 city map. "
            "Read the map code: a circled numeral like 16 or (1), or a letter+digit like B3, A11, D4. "
            "Ignore the circle itself. Return ONLY JSON: "
            '{"raw":"what you see","candidates":[{"id":"LEXICON_ID","why":"short"}]} '
            "with up to 5 ids from this lexicon, best first: " + lex
        )
        raw = xai_vision(key, image_url, prompt)
        if isinstance(raw, dict) and raw.get("error"):
            self._json(raw.get("status") or 502, raw)
            return
        text = extract_text(raw)
        parsed = parse_model_json(text)
        parsed["raw_model"] = text
        self._json(200, parsed)

    def _find_text(self, key, image_url, query):
        if not query:
            self._json(400, {"error": "missing query"})
            return
        prompt = (
            "This is a fragment of a hand-drawn ~1939 city map (ink on paper). "
            "Find EVERY occurrence of this exact map code / number / short string: %r. "
            "It may be handwritten, inside a circle, next to a street, or standing alone. "
            "Do NOT match a different number that only shares some digits "
            "(query %r must not match 1, 6, 61, 160, etc. if those are different codes). "
            "Ignore street names that merely contain the digits as part of a longer word. "
            "Return ONLY JSON of the form "
            '{"hits":[{"x_pct":12.5,"y_pct":40.0,"w_pct":3.0,"h_pct":3.5,"text":"%s"}]} '
            "where x_pct and y_pct are the CENTER of the match as percentages of THIS image "
            "(0 = left/top, 100 = right/bottom). w_pct/h_pct are the box size in the same units. "
            "If you see none, return {\"hits\":[]}."
        ) % (query, query, query.replace('"', ""))
        raw = xai_vision(key, image_url, prompt)
        if isinstance(raw, dict) and raw.get("error"):
            self._json(raw.get("status") or 502, raw)
            return
        text = extract_text(raw)
        parsed = parse_find_hits(text, query)
        parsed["raw_model"] = text[:500]
        self._json(200, parsed)

    def _json(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def xai_vision(key: str, image_url: str, prompt: str):
    payload = {
        "model": MODEL,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_image", "image_url": image_url, "detail": "high"},
                    {"type": "input_text", "text": prompt},
                ],
            }
        ],
    }
    req = urllib.request.Request(
        API,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + key,
        },
        method="POST",
    )
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=180) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", "replace")[:800]
        return {"error": "xAI HTTP %s" % e.code, "detail": err, "status": e.code}
    except Exception as e:
        return {"error": str(e), "status": 502}


def extract_text(raw: dict) -> str:
    if isinstance(raw.get("output_text"), str) and raw["output_text"].strip():
        return raw["output_text"]
    chunks = []
    for item in raw.get("output") or []:
        for c in item.get("content") or []:
            if c.get("type") in ("output_text", "text") and c.get("text"):
                chunks.append(c["text"])
    return "\n".join(chunks)


def parse_model_json(text: str) -> dict:
    text = (text or "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            obj = json.loads(text[start : end + 1])
            cands = obj.get("candidates") or []
            clean = []
            for c in cands:
                if isinstance(c, dict) and c.get("id"):
                    clean.append(
                        {"id": str(c["id"]).strip(), "why": str(c.get("why") or "vision")}
                    )
                elif isinstance(c, str):
                    clean.append({"id": c.strip(), "why": "vision"})
            return {"raw": str(obj.get("raw") or ""), "candidates": clean[:5]}
        except Exception:
            pass
    return {"raw": text[:80], "candidates": []}


def _pct(v, fallback=3.0):
    try:
        n = float(v)
    except (TypeError, ValueError):
        return fallback
    if n <= 1.5:
        n *= 100.0
    return max(0.0, min(100.0, n))


def parse_find_hits(text: str, query: str) -> dict:
    text = (text or "").strip()
    start, end = text.find("{"), text.rfind("}")
    hits = []
    if start >= 0 and end > start:
        try:
            obj = json.loads(text[start : end + 1])
            raw_hits = obj.get("hits") or obj.get("matches") or []
            for h in raw_hits:
                if not isinstance(h, dict):
                    continue
                x = h.get("x_pct", h.get("x", h.get("cx")))
                y = h.get("y_pct", h.get("y", h.get("cy")))
                if x is None or y is None:
                    continue
                xp, yp = _pct(x, -1), _pct(y, -1)
                if xp < 0 or yp < 0:
                    continue
                hits.append(
                    {
                        "x_pct": xp,
                        "y_pct": yp,
                        "w_pct": _pct(h.get("w_pct", h.get("w")), 3.0),
                        "h_pct": _pct(h.get("h_pct", h.get("h")), 3.0),
                        "text": str(h.get("text") or query).strip(),
                    }
                )
        except Exception:
            pass
    return {"hits": hits}


def main() -> None:
    if not os.environ.get("XAI_API_KEY"):
        print("warning: XAI_API_KEY is not set; vision endpoints will fail until it is")
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(
        "label OCR proxy on http://%s:%s  (POST /find-text, /read-label, GET /health)"
        % (HOST, PORT)
    )
    httpd.serve_forever()


if __name__ == "__main__":
    main()
