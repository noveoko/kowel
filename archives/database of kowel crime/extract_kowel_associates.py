#!/usr/bin/env python3
"""Build the Kowel-city crime table from harvested Gazeta Śledcza OCR.

Keeps a wanted-person entry if it is tied to Kowel *city* by any of:

  last_address     — lived in Kowel (ost./st. zam., mieszk. Kowla)
  wanted_by_city   — sought by a court / sędzia / starosta / prosecutor in Kowel
  arrested_in_city — caught, jailed, or escaped from jail in Kowel
  offence_in_city  — theft/assault/etc. described as done in Kowel
  victim_in_city   — harm to someone in Kowel (na szkodę … w Kowlu)

County-only hits (pow. kowelskiego, village last address, no city organ)
are not kept. The old resident-only 123-row file is left at
kowel_criminal_database_residents.csv.

    uv run python extract_kowel_associates.py
"""

from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path

from gazeta_parser import (
    KOWEL_RESIDENT_RE,
    clean_text,
    extract_address,
    extract_age_or_birth,
    extract_charge_codes,
    extract_name,
    charge_lookup,
    split_entries,
)

UUID_RE = re.compile(
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.I,
)
DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")

# --- city (not powiat) ---
LIVE_RE = re.compile(
    r"(?:ost\W{0,4}za\w{1,4}|st\.?\s*za\w{1,4}|mieszk\w*)\W{0,8}(?:w\s+)?Kowl",
    re.I,
)
LIVE_PRZY_RE = re.compile(r"w\s+Kowl\w*\s+przy", re.I)

WANTED_RE = re.compile(
    r"(?:"
    r"posz\w*\W{0,16}przez\W{0,40}"
    r"(?:S[aą]d\w*|S[eę]dzie\w*|Prokur\w*|Starost\w*)\W{0,50}w\s*Kowl"
    r"|"
    r"S[aą]d(?:u)?\s*P\.?\s*w\s*Kowl"
    r"|"
    r"S[aą]d\w*\s*Grodzk\w*\s*w\s*Kowl"
    r"|"
    r"S[eę]dzie\w*.{0,50}w\s*Kowl"
    r"|"
    r"Starost\w*\s*w\s*Kowl"
    r"|"
    r"Prokur\w*.{0,30}w\s*Kowl"
    r"|"
    r"Wojsk\w*\s*S[aą]d\w*.{0,25}w\s*Kowl"
    r"|"
    r"Urz\w*\W{0,12}(?:P\.?\s*)?Śledcz\w*.{0,25}Kowl"
    r"|"
    r"więzieni\w*(?:um|u|a)?\s+(?:powiatow\w*\s+)?w\s*Kowl"
    r")",
    re.I,
)

# Past detention in Kowel, not the formula "w razie ujęcia odesłać do więzienia w Kowlu".
ARRESTED_RE = re.compile(
    r"(?:"
    r"ujęt\w+\s+i\s+osadzon\w*\W{0,8}w?\W{0,8}więzieni\w*.{0,30}Kowl"
    r"|"
    r"został\s+ujęt\w*.{0,50}więzieni\w*.{0,30}Kowl"
    r"|"
    r"zbieg\w*.{0,40}z\s+więzieni\w*.{0,30}Kowl"
    r")",
    re.I,
)

OFFENCE_RE = re.compile(
    r"(?:"
    r"(?:skradziono|dokona\w*\s+kradzie|popełn\w*\s+\w+)\s*.{0,40}w\s*Kowl"
    r"|"
    r"w\s*Kowl\w*,?\s+(?:skradziono|dokona\w*|popełn\w*|kradzie[zż]\w*|rozb[oó]j|napad\w*)"
    r")",
    re.I,
)

VICTIM_RE = re.compile(
    r"(?:"
    r"na\s+szkod[eę].{0,90}Kowl"
    r"|"
    r"pokrzywdz\w*.{0,50}Kowl"
    r"|"
    r"Kowl.{0,70}na\s+szkod"
    r")",
    re.I,
)

SKIP_NAME_RE = re.compile(
    r"(?i)^(skorowidz|zagubiony|n\.?\s*$|\d+$)",
)

CITY_TAGS = (
    "last_address",
    "wanted_by_city",
    "arrested_in_city",
    "offence_in_city",
    "victim_in_city",
)

FIELDS = [
    "Name",
    "Age / Birth Year",
    "Last Known Address in Kowel",
    "Penal Code Charge",
    "Legal Charge in English",
    "kowel_link",
    "object_id",
    "issue_title",
    "issue_date",
    "source_url",
    "excerpt",
]


def classify(body: str) -> list[str]:
    tags = []
    if KOWEL_RESIDENT_RE.search(body) or LIVE_RE.search(body) or LIVE_PRZY_RE.search(body):
        tags.append("last_address")
    if WANTED_RE.search(body):
        tags.append("wanted_by_city")
    if ARRESTED_RE.search(body):
        tags.append("arrested_in_city")
    if OFFENCE_RE.search(body):
        tags.append("offence_in_city")
    if VICTIM_RE.search(body):
        tags.append("victim_in_city")
    return tags


def keep_name(name: str) -> bool:
    name = (name or "").strip()
    if len(name) < 3:
        return False
    if SKIP_NAME_RE.search(name):
        return False
    return True


def meta_from_name(path: Path) -> dict:
    name = path.name
    oid = UUID_RE.search(name)
    date = DATE_RE.match(name)
    object_id = oid.group(1) if oid else ""
    title = name[: oid.start()].rstrip("_") if oid else name
    return {
        "object_id": object_id,
        "issue_date": date.group(1) if date else "",
        "issue_title": title,
        "source_url": f"https://polona.pl/preview/{object_id}" if object_id else "",
    }


def main() -> None:
    ocr_dir = Path("data/kowel_criminal_database/ocr")
    out_main = Path("data/kowel_criminal_database/kowel_criminal_database.csv")
    out_assoc = Path("data/kowel_criminal_database/kowel_associates.csv")
    rows = []
    n_files = 0
    for path in sorted(ocr_dir.glob("*.txt")):
        n_files += 1
        meta = meta_from_name(path)
        raw = path.read_text(encoding="utf-8", errors="replace")
        for e in split_entries(clean_text(raw)):
            body = e["body"]
            tags = classify(body)
            if not tags:
                continue
            name = extract_name(body)
            if not keep_name(name):
                continue
            codes = extract_charge_codes(body)
            rows.append(
                {
                    "Name": name,
                    "Age / Birth Year": extract_age_or_birth(body),
                    "Last Known Address in Kowel": extract_address(body),
                    "Penal Code Charge": ", ".join(f"art. {c}" for c in codes),
                    "Legal Charge in English": charge_lookup(codes) if codes else "",
                    "kowel_link": ";".join(tags),
                    "object_id": meta["object_id"],
                    "issue_title": meta["issue_title"],
                    "issue_date": meta["issue_date"],
                    "source_url": meta["source_url"],
                    "excerpt": re.sub(r"\s+", " ", body)[:320],
                }
            )

    with out_main.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    with out_assoc.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    tag_c = Counter()
    combo_c = Counter()
    names = set()
    for r in rows:
        names.add(r["Name"])
        combo_c[r["kowel_link"]] += 1
        for t in r["kowel_link"].split(";"):
            tag_c[t] += 1

    print(f"Scanned {n_files} OCR files. City-tied rows={len(rows)} distinct names={len(names)}")
    print("tag counts (a row may have several):")
    for k in CITY_TAGS:
        print(f"  {k:20} {tag_c[k]}")
    print("top combos:")
    for k, v in combo_c.most_common(8):
        print(f"  {v:5} {k}")
    print(f"Wrote {out_main}")
    print("Resident-only copy: data/kowel_criminal_database/kowel_criminal_database_residents.csv")


if __name__ == "__main__":
    main()
