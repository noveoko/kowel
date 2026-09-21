#!/usr/bin/env python3
"""Parse Kowel commercial-register notices from Obwieszczenia Publiczne OCR.

Typical pair (Rejestr handlowy), as in R.8 № 74 (16 sierpnia 1924):

    „Żurach Zafran”, handel żelazem w Kowlu, ul. Lucka 16. Istnieje od 1893 r. Właśc.
    Laks Chaskiel, zam. w Kowlu, przy ul. Aptecznej 36. d. 25 kwietnia 1924 r. 1196.

OCR splits "Istnieje", "zam.", "przy ul." — this matcher is loose on purpose.
Street names are left as written (declined forms).
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

QMARKS = "„“”\"«»"
KOWL = r"Kowl\w*"

FIRM_RE = re.compile(
    rf"[{QMARKS}](?P<firm>[^{QMARKS}]{{2,80}})[{QMARKS}]\s*[,—–\-]+\s*"
    rf"(?P<kind>[^.]{{1,80}}?)\s+"
    rf"w\s+{KOWL}\s*,?\s*"
    rf"(?:ul\.?|ulicy)?\s*"
    rf"(?P<street>.*?)(?=\s*Istniej|\s*Właśc|\s*zam\w*|[A-ZĄĆĘŁŃÓŚŹŻ][\w\-]*\s+(?!Istniej|Właśc)[A-ZĄĆĘŁŃÓŚŹŻ]|\.|$)"
    rf"(?:\.\s*)?\s*"
    rf"(?:Istniej\w*(?:\s+\S+){{0,3}}\s+od\s+(?P<since>\d{{4}}|\d+\s+\w+|\d+\s+lat)\s*r\.?)?"
    rf"(?:\s*Właśc\w*\.?)?",
    re.IGNORECASE,
)

OWNER_RE = re.compile(
    rf"(?:(?<=^)|(?<=[\d.])\s+|(?<=[—–\-])\s*)"
    rf"(?P<name>(?:[A-ZĄĆĘŁŃÓŚŹŻ][\w\-]*\s+){{1,3}}[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż\-]{{1,40}}),\s*"
    rf"zam\w*[.,]?\s*w\s+{KOWL}\s*[.,]?\s*"
    rf"(?:przy|pr\s*z)?\s*(?:[{QMARKS}]\s*)?(?:ul\.?|ulicy)?\s*"
    rf"(?P<street>[^.{QMARKS}]{{2,40}})"
    rf"(?:\.\s*d\.\s*(?P<notice_date>\d{{1,2}}\s+\w+\s+\d{{4}})\s*r\.?)?"
    rf"(?:[.\s]+(?P<reg>\d{{3,5}}))?",
)

FIELDS = [
    "firm_name",
    "business_type",
    "firm_street",
    "exists_since",
    "owner_name",
    "owner_street",
    "register_no",
    "notice_date",
    "raw",
]


def clean_ocr(raw: str) -> str:
    raw = raw.replace("\u00ad", "")
    raw = re.sub(r"I\s+st\s+nieje", "Istnieje", raw, flags=re.I)
    raw = re.sub(r"Ist\s+nieje", "Istnieje", raw, flags=re.I)
    raw = re.sub(r"\s+", " ", raw)
    return raw.strip()


def _tidy(s: str | None) -> str:
    if not s:
        return ""
    s = re.sub(r"\s+", " ", s).strip(" ,.—–-;:")
    s = re.sub(r"\s*Właśc\w*\.?$", "", s, flags=re.I).strip()
    return s


def parse_text(raw: str) -> list[dict]:
    text = clean_ocr(raw)
    firm_matches = list(FIRM_RE.finditer(text))
    owner_matches = list(OWNER_RE.finditer(text))
    used_owners: set[int] = set()
    rows: list[dict] = []

    def owner_after(pos: int, until: int | None) -> tuple[int | None, re.Match[str] | None]:
        for i, om in enumerate(owner_matches):
            if i in used_owners:
                continue
            if om.start() < pos and text[om.start() : pos].strip():
                continue
            if until is not None and om.start() >= until:
                continue
            return i, om
        return None, None

    for i, fm in enumerate(firm_matches):
        until = firm_matches[i + 1].start() if i + 1 < len(firm_matches) else None
        window = text[fm.end() : until]
        oi, om = owner_after(fm.end(), until)
        if om and (
            (om.start() - fm.end()) > 180
            or re.search(r"\bStrona\s+\d+\b", window[: om.start() - fm.end()], re.I)
        ):
            om = None
            oi = None
        if oi is not None:
            used_owners.add(oi)
        street = _tidy(fm.group("street"))
        if street.lower() in {"ul", "ul."}:
            street = ""
        if re.match(
            r"[A-ZĄĆĘŁŃÓŚŹŻ][\w\-]*(?:\s+[A-ZĄĆĘŁŃÓŚŹŻ][\w\-]*)+$",
            street,
        ):
            street = ""
        row = {
            "firm_name": _tidy(fm.group("firm")),
            "business_type": _tidy(fm.group("kind")),
            "firm_street": street,
            "exists_since": _tidy(fm.group("since")),
            "owner_name": _tidy(om.group("name")) if om else "",
            "owner_street": _tidy(om.group("street")) if om else "",
            "register_no": _tidy(om.group("reg")) if om else "",
            "notice_date": _tidy(om.group("notice_date")) if om else "",
            "raw": _tidy(text[fm.start() : (om.end() if om else fm.end())])[:400],
        }
        rows.append(row)

    for i, om in enumerate(owner_matches):
        if i in used_owners:
            continue
        rows.append(
            {
                "firm_name": "",
                "business_type": "",
                "firm_street": "",
                "exists_since": "",
                "owner_name": _tidy(om.group("name")),
                "owner_street": _tidy(om.group("street")),
                "register_no": _tidy(om.group("reg")),
                "notice_date": _tidy(om.group("notice_date")),
                "raw": _tidy(om.group(0)[:400]),
            }
        )
    return rows


def parse_file(path: Path) -> list[dict]:
    return parse_text(path.read_text(encoding="utf-8", errors="replace"))


def write_csv(rows: list[dict], output_path: Path, extra_fields: list[str] | None = None) -> None:
    fields = FIELDS + (extra_fields or [])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
