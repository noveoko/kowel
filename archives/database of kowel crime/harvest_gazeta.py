#!/usr/bin/env python3
"""Harvest Gazeta Śledcza OCR from Polona and parse Kowel wanted-person entries.

Uses the current search-service API. Does not call /api/entities/ (gone)
and does not use pypolona.

Default: only issues whose OCR mentions Kowel/Kowlu/Kowla, then
gazeta_parser.py for last-address-in-Kowel rows.

    uv run python harvest_gazeta.py --out data/gazeta_sledcza
    uv run python harvest_gazeta.py --out data/gazeta_sledcza --limit 2
    uv run python harvest_gazeta.py --out data/gazeta_sledcza --object-id <uuid>
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path

from gazeta_parser import parse_text, write_csv
from polona_client import (
    GAZETA_SLEDCA_IDENTIFICATION_ID,
    GAZETA_SLEDCA_TITLE,
    first_value,
    iter_fulltext,
    iter_identification,
    download_ocr_zip,
    object_hit,
    ocr_text_from_zip,
    preview_url,
    session as polona_session,
)

KOWEL_QUERIES = ("Kowlu", "Kowel", "Kowla")
CSV_FIELDS = [
    "Name",
    "Age / Birth Year",
    "Last Known Address in Kowel",
    "Penal Code Charge",
    "Legal Charge in English",
    "object_id",
    "issue_title",
    "issue_date",
    "source_url",
]


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


def collect_kowel_issues(sess, sleep: float, limit: int | None = None) -> dict[str, dict]:
    issues: dict[str, dict] = {}
    for query in KOWEL_QUERIES:
        log(f"Fulltext '{query}' in title {GAZETA_SLEDCA_TITLE!r}...")
        n = 0
        for hit in iter_fulltext(sess, query):
            info = hit_summary(hit)
            oid = info["object_id"]
            if oid and oid not in issues:
                issues[oid] = info
            n += 1
            if limit and len(issues) >= limit:
                log(f"  {n} page hits, {len(issues)} unique issues (limit)")
                return issues
        log(f"  {n} page hits, {len(issues)} unique issues so far")
        time.sleep(sleep)
    return issues


def collect_all_issues(sess, sleep: float, limit: int | None = None) -> dict[str, dict]:
    issues: dict[str, dict] = {}
    log(f"Listing serial {GAZETA_SLEDCA_IDENTIFICATION_ID}...")
    for i, hit in enumerate(iter_identification(sess), 1):
        info = hit_summary(hit)
        oid = info["object_id"]
        if oid:
            issues[oid] = info
        if i % 50 == 0:
            log(f"  listed {i} issues")
            time.sleep(sleep)
        if limit and len(issues) >= limit:
            break
    return issues


def log(msg: str) -> None:
    print(msg, flush=True)


def write_database(rows: list[dict], csv_path: Path, native_path: Path) -> None:
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    native_fields = [
        "Name",
        "Age / Birth Year",
        "Last Known Address in Kowel",
        "Penal Code Charge",
        "Legal Charge in English",
    ]
    write_csv([{k: r[k] for k in native_fields} for r in rows], native_path)


def harvest_one(sess, info: dict, ocr_dir: Path, sleep: float, skip_existing: bool) -> str | None:
    oid = info["object_id"]
    date = (info.get("date") or "undated").replace(":", "-")
    fname = f"{date}_{slugify(info.get('title') or '')}_{oid}.txt"
    path = ocr_dir / fname
    if skip_existing and path.exists() and path.stat().st_size > 0:
        return path.read_text(encoding="utf-8", errors="replace")
    blob = download_ocr_zip(sess, oid)
    text = ocr_text_from_zip(blob)
    path.write_text(text, encoding="utf-8")
    time.sleep(sleep)
    return text


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data/gazeta_sledcza", help="Output folder")
    ap.add_argument("--limit", type=int, default=None, help="Stop after N issues")
    ap.add_argument("--sleep", type=float, default=0.4, help="Seconds between Polona calls")
    ap.add_argument("--all-issues", action="store_true", help="All serial issues, not only Kowel OCR hits")
    ap.add_argument("--object-id", action="append", default=[], help="Harvest this UUID (repeatable)")
    ap.add_argument("--no-skip-existing", action="store_true", help="Re-download OCR even if txt exists")
    args = ap.parse_args(argv)

    out_dir = Path(args.out)
    ocr_dir = out_dir / "ocr"
    ocr_dir.mkdir(parents=True, exist_ok=True)
    for sentinel in ("HARVEST_OK", "HARVEST_FAIL"):
        p = out_dir / sentinel
        if p.exists():
            p.unlink()
    manifest_path = out_dir / "manifest.jsonl"
    csv_path = out_dir / "kowel_criminal_database.csv"
    native_path = out_dir / "kowel_wanted_parser.csv"
    skip_existing = not args.no_skip_existing

    sess = polona_session()
    issues: dict[str, dict] = {}

    if args.object_id:
        for oid in args.object_id:
            hit = object_hit(sess, oid)
            issues[oid] = hit_summary(hit)
            time.sleep(args.sleep)
    elif args.all_issues:
        issues = collect_all_issues(sess, args.sleep, args.limit)
    else:
        issues = collect_kowel_issues(sess, args.sleep, args.limit)

    items = list(issues.values())
    items.sort(key=lambda x: (x.get("date") or "", x.get("title") or ""))
    if args.limit is not None:
        items = items[: args.limit]

    log(f"Harvesting OCR for {len(items)} issues -> {ocr_dir}")

    all_rows: list[dict] = []
    n_ok = 0
    n_fail = 0
    exit_code = 1

    try:
        with open(manifest_path, "w", encoding="utf-8") as manifest:
            for i, info in enumerate(items, 1):
                oid = info["object_id"]
                log(f"[{i}/{len(items)}] {info.get('date')} {info.get('title')} [{oid}]")
                record = dict(info)
                try:
                    text = harvest_one(sess, info, ocr_dir, args.sleep, skip_existing)
                except Exception as e:
                    log(f"   FAILED OCR: {e}")
                    record["error"] = str(e)
                    manifest.write(json.dumps(record, ensure_ascii=False) + "\n")
                    manifest.flush()
                    n_fail += 1
                    continue
                n_ok += 1
                rows, warnings = parse_text(text or "")
                record["kowel_rows"] = len(rows)
                record["warnings"] = len(warnings)
                manifest.write(json.dumps(record, ensure_ascii=False) + "\n")
                manifest.flush()
                for row in rows:
                    row = dict(row)
                    row["object_id"] = oid
                    row["issue_title"] = info.get("title") or ""
                    row["issue_date"] = info.get("date") or ""
                    row["source_url"] = info.get("url") or ""
                    all_rows.append(row)
                write_database(all_rows, csv_path, native_path)
                for w in warnings:
                    log(w)

        write_database(all_rows, csv_path, native_path)
        log(f"OCR ok={n_ok} fail={n_fail}. Kowel-resident rows={len(all_rows)}")
        log(f"CSV: {csv_path}")
        log(f"Manifest: {manifest_path}")
        exit_code = 0 if n_ok > 0 else 1
    except Exception as e:
        log(f"HARVEST ABORTED: {e}")
        exit_code = 1
        raise
    finally:
        status = out_dir / ("HARVEST_OK" if exit_code == 0 else "HARVEST_FAIL")
        status.write_text(
            json.dumps({"ok": n_ok, "fail": n_fail, "rows": len(all_rows), "exit": exit_code}),
            encoding="utf-8",
        )

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
