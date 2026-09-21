#!/usr/bin/env python3
"""Harvest Obwieszczenia Publiczne editions whose OCR contains "w Kowlu".

Separate from harvest_gazeta.py: no wanted-person parser. Writes a page-snippet
index plus (unless --snippets-only) OCR text for each matching edition.

    uv run python harvest_obwieszczenia.py --out data/obwieszczenia_publiczne
    uv run python harvest_obwieszczenia.py --out data/obwieszczenia_publiczne --limit 2
    uv run python harvest_obwieszczenia.py --out data/obwieszczenia_publiczne --snippets-only
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path

from polona_client import (
    download_ocr_zip,
    first_value,
    iter_fulltext,
    ocr_text_from_zip,
    preview_url,
    session as polona_session,
)

TITLE = "Obwieszczenia Publiczne"
QUERY = '"w Kowlu"'
SNIPPET_FIELDS = [
    "object_id",
    "issue_title",
    "issue_date",
    "page",
    "highlight",
    "source_url",
]


def log(msg: str) -> None:
    print(msg, flush=True)


def slugify(text: str, maxlen: int = 80) -> str:
    text = re.sub(r"[^\w\-]+", "_", text, flags=re.UNICODE)
    return text.strip("_")[:maxlen] or "untitled"


def hit_summary(hit: dict) -> dict:
    object_id = hit.get("objectId") or ""
    title = first_value(hit, "title")
    date = first_value(hit, "date") or first_value(hit, "dateDescriptive")
    return {
        "object_id": object_id,
        "title": title,
        "date": date,
        "url": preview_url(object_id) if object_id else "",
    }


def highlight_text(hit: dict) -> str:
    parts = hit.get("highlights") or []
    text = " ".join(str(p) for p in parts)
    return re.sub(r"<[^>]+>", "", text)


def collect_hits(sess, sleep: float, limit: int | None) -> tuple[dict[str, dict], list[dict]]:
    issues: dict[str, dict] = {}
    snippets: list[dict] = []
    n = 0
    log(f"Fulltext {QUERY} in title {TITLE!r}...")
    for hit in iter_fulltext(sess, QUERY, title=TITLE):
        info = hit_summary(hit)
        oid = info["object_id"]
        if not oid:
            continue
        is_new = oid not in issues
        if is_new and limit is not None and len(issues) >= limit:
            continue
        if is_new:
            issues[oid] = info
            issues[oid]["n_hits"] = 0
        issues[oid]["n_hits"] = int(issues[oid].get("n_hits") or 0) + 1
        snippets.append(
            {
                "object_id": oid,
                "issue_title": info["title"],
                "issue_date": info["date"],
                "page": hit.get("pageNumber") or "",
                "highlight": highlight_text(hit),
                "source_url": info["url"],
            }
        )
        n += 1
        if limit is not None and len(issues) >= limit and is_new:
            log(f"  {n} page hits, {len(issues)} unique editions (limit)")
            break
        if n % 100 == 0:
            log(f"  {n} page hits, {len(issues)} unique editions")
            time.sleep(sleep)
    else:
        log(f"  {n} page hits, {len(issues)} unique editions")
    return issues, snippets


def write_snippets(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SNIPPET_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def harvest_one(sess, info: dict, ocr_dir: Path, sleep: float, skip_existing: bool) -> tuple[str, str]:
    oid = info["object_id"]
    date = (info.get("date") or "undated").replace(":", "-")
    fname = f"{date}_{slugify(info.get('title') or '')}_{oid}.txt"
    path = ocr_dir / fname
    if skip_existing and path.exists() and path.stat().st_size > 0:
        return fname, path.read_text(encoding="utf-8", errors="replace")
    blob = download_ocr_zip(sess, oid)
    text = ocr_text_from_zip(blob)
    path.write_text(text, encoding="utf-8")
    time.sleep(sleep)
    return fname, text


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data/obwieszczenia_publiczne", help="Output folder")
    ap.add_argument("--limit", type=int, default=None, help="Stop after N unique editions")
    ap.add_argument("--sleep", type=float, default=0.4, help="Seconds between Polona calls")
    ap.add_argument("--snippets-only", action="store_true", help="Write snippet CSV, skip OCR zips")
    ap.add_argument("--no-skip-existing", action="store_true", help="Re-download OCR even if txt exists")
    args = ap.parse_args(argv)

    out_dir = Path(args.out)
    ocr_dir = out_dir / "ocr"
    ocr_dir.mkdir(parents=True, exist_ok=True)
    for sentinel in ("HARVEST_OK", "HARVEST_FAIL"):
        p = out_dir / sentinel
        if p.exists():
            p.unlink()

    snippet_path = out_dir / "kowel_snippets.csv"
    manifest_path = out_dir / "manifest.jsonl"
    skip_existing = not args.no_skip_existing

    issues: dict[str, dict] = {}
    snippets: list[dict] = []
    n_ok = 0
    n_fail = 0
    exit_code = 1

    try:
        sess = polona_session()
        issues, snippets = collect_hits(sess, args.sleep, args.limit)
        write_snippets(snippet_path, snippets)
        log(f"Wrote {len(snippets)} snippets -> {snippet_path}")

        items = sorted(issues.values(), key=lambda x: (x.get("date") or "", x.get("title") or ""))
        with open(manifest_path, "w", encoding="utf-8") as manifest:
            if args.snippets_only:
                for info in items:
                    manifest.write(json.dumps(info, ensure_ascii=False) + "\n")
                n_ok = len(items)
            else:
                log(f"Harvesting OCR for {len(items)} editions -> {ocr_dir}")
                for i, info in enumerate(items, 1):
                    log(f"[{i}/{len(items)}] {info.get('date')} {info.get('title')} [{info.get('object_id')}]")
                    record = dict(info)
                    try:
                        fname, _text = harvest_one(sess, info, ocr_dir, args.sleep, skip_existing)
                        record["ocr_file"] = fname
                        n_ok += 1
                    except Exception as e:
                        log(f"   FAILED OCR: {e}")
                        record["error"] = str(e)
                        n_fail += 1
                    manifest.write(json.dumps(record, ensure_ascii=False) + "\n")
                    manifest.flush()

        log(f"OCR ok={n_ok} fail={n_fail}. snippets={len(snippets)} editions={len(issues)}")
        exit_code = 0 if (args.snippets_only and snippets) or n_ok > 0 else 1
    except Exception as e:
        log(f"HARVEST ABORTED: {e}")
        exit_code = 1
        raise
    finally:
        status = out_dir / ("HARVEST_OK" if exit_code == 0 else "HARVEST_FAIL")
        status.write_text(
            json.dumps(
                {
                    "ok": n_ok,
                    "fail": n_fail,
                    "snippets": len(snippets),
                    "editions": len(issues),
                    "exit": exit_code,
                }
            ),
            encoding="utf-8",
        )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
