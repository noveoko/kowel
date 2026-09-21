#!/usr/bin/env python3
"""Scan harvested Obwieszczenia OCR and write a Kowel business/owner CSV.

Safe to re-run while harvest_obwieszczenia.py is still downloading; it only
reads files already in --ocr-dir.

    uv run python parse_obwieszczenia.py
    uv run python parse_obwieszczenia.py --ocr-dir data/obwieszczenia_publiczne/ocr
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from obwieszczenia_parser import parse_file, write_csv

UUID_RE = re.compile(
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.I,
)
DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


def meta_from_name(path: Path) -> dict:
    name = path.name
    oid = UUID_RE.search(name)
    date = DATE_RE.match(name)
    object_id = oid.group(1) if oid else ""
    return {
        "issue_date": date.group(1) if date else "",
        "object_id": object_id,
        "source_url": f"https://polona.pl/preview/{object_id}" if object_id else "",
        "ocr_file": name,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ocr-dir", default="data/obwieszczenia_publiczne/ocr")
    ap.add_argument("--out", default="data/obwieszczenia_publiczne/kowel_businesses.csv")
    args = ap.parse_args(argv)

    ocr_dir = Path(args.ocr_dir)
    if not ocr_dir.is_dir():
        print(f"No OCR dir yet: {ocr_dir}", file=sys.stderr)
        return 1

    extra = ["issue_date", "object_id", "source_url", "ocr_file"]
    rows: list[dict] = []
    n_files = 0
    for path in sorted(ocr_dir.glob("*.txt")):
        n_files += 1
        meta = meta_from_name(path)
        for row in parse_file(path):
            row.update(meta)
            rows.append(row)

    out = Path(args.out)
    write_csv(rows, out, extra_fields=extra)
    n_firms = sum(1 for r in rows if r.get("firm_name"))
    n_owners = sum(1 for r in rows if r.get("owner_name"))
    print(f"Scanned {n_files} OCR files. Rows={len(rows)} firms={n_firms} owners={n_owners}")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
