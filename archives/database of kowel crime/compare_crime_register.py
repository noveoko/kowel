#!/usr/bin/env python3
"""Find people who appear in both Gazeta Śledcza (crime) and Obwieszczenia (register)."""

from __future__ import annotations

import csv
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

DIACRITIC = str.maketrans(
    "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ",
    "acelnoszzACELNOSZZ",
)
STOP = frozenset(
    "s syn c corka zona zam w kowlu przy ul ulicy i".split()
)
GIVEN = frozenset(
    """
    adam aleksander abram antoni antonina anna andrzej
    benjamin berko bluma
    chaim chaja
    dawid dora
    edward eliasz elka
    feliks franciszek franciszka
    gdal gitla grzegorz
    helena henryk hersz
    icchek icchok icko izaak izrael
    jan janina jadwiga jakob jakub jankiel jenta jerzy jozef jozefa julia
    kazimierz
    lcchok lejb lejzor leon liba
    marcin maria marian marjan marja mendel michal mieczyslaw mikolaj mordko moszek
    nadzieja nuchim
    olga
    pinchas
    rachmil ruchla ruchla
    stanislaw stanislawa stefan szloma szmul
    teodor
    waclaw weronika wincenty wladyslaw wolf
    zajwel zofia zygmunt
    """.split()
)


def fold(s: str) -> str:
    s = (s or "").replace("\\", " ")
    s = s.translate(DIACRITIC)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s\-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def tokens(s: str) -> list[str]:
    parts = fold(s).replace("-", " ").split()
    collapsed: list[str] = []
    buf: list[str] = []
    for p in parts:
        if len(p) == 1:
            buf.append(p)
            continue
        if buf:
            collapsed.append("".join(buf))
            buf = []
        collapsed.append(p)
    if buf:
        collapsed.append("".join(buf))
    out = [p for p in collapsed if p and p not in STOP and len(p) > 1]
    return out


def surname_given(toks: list[str]) -> tuple[str, str]:
    if not toks:
        return "", ""
    if len(toks) == 1:
        return toks[0], ""
    # Crime gazettes: Surname Given. Register: Given Surname.
    # Use the longest token as surname when lengths differ a lot; else both orders.
    return toks[0], toks[-1]


def score_pair(crime_toks: list[str], other_toks: list[str]) -> tuple[float, str]:
    if not crime_toks or not other_toks:
        return 0.0, ""
    a, b = set(crime_toks), set(other_toks)
    if a == b and len(a) >= 2:
        return 1.0, "token_set"
    if len(a & b) >= 2:
        shared = sorted(a & b)
        if any(t not in GIVEN and len(t) >= 4 for t in shared) and min(len(t) for t in shared) >= 3:
            return 0.92, "two_tokens:" + "+".join(shared)
    def surnames(toks: list[str]) -> list[str]:
        sur = [t for t in toks if t not in GIVEN and len(t) >= 4]
        return sur or [t for t in toks if len(t) >= 5]

    # surname equality either order + first-name prefix
    for c_sur in surnames(crime_toks):
        for o_sur in surnames(other_toks):
            if len(c_sur) < 4 or len(o_sur) < 4:
                continue
            ratio = SequenceMatcher(None, c_sur, o_sur).ratio()
            if c_sur == o_sur or (ratio >= 0.9 and abs(len(c_sur) - len(o_sur)) <= 2):
                c_rest = [t for t in crime_toks if t != c_sur]
                o_rest = [t for t in other_toks if t != o_sur]
                if not c_rest or not o_rest:
                    if c_sur == o_sur and len(c_sur) >= 6:
                        return 0.7, f"surname_only:{c_sur}"
                    continue
                # given name match or initial
                for cg in c_rest:
                    for og in o_rest:
                        if cg == og and len(cg) >= 3:
                            why = "surname+given" if c_sur == o_sur else f"fuzzy_surname:{c_sur}~{o_sur}"
                            return (0.95 if c_sur == o_sur else 0.88), why
                        if len(cg) >= 3 and len(og) >= 3 and cg[0] == og[0] and (
                            cg.startswith(og[:3]) or og.startswith(cg[:3])
                        ):
                            return 0.85, f"surname+given_prefix:{c_sur}/{cg}~{og}"
    return 0.0, ""


def load_crime(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            name = (r.get("Name") or "").split(",")[0]
            name = re.split(r"\bs\.\s", name)[0].strip()
            toks = tokens(name)
            if toks:
                r = dict(r)
                r["_name"] = name
                r["_toks"] = toks
                rows.append(r)
    return rows


def load_register(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            for field in ("owner_name", "firm_name"):
                name = (r.get(field) or "").strip()
                toks = tokens(name)
                if len(toks) < 1:
                    continue
                item = dict(r)
                item["_name"] = name
                item["_toks"] = toks
                item["_role"] = field
                rows.append(item)
    return rows


def main() -> None:
    crime_path = Path("data/kowel_criminal_database/kowel_criminal_database.csv")
    biz_path = Path("data/obwieszczenia_publiczne/kowel_businesses.csv")
    out_path = Path("data/overlap_crime_register.csv")

    crime = load_crime(crime_path)
    register = load_register(biz_path)

    hits: list[dict] = []
    for c in crime:
        best: list[tuple[float, str, dict]] = []
        for b in register:
            sc, why = score_pair(c["_toks"], b["_toks"])
            if sc >= 0.85:
                best.append((sc, why, b))
        best.sort(key=lambda x: -x[0])
        seen = set()
        for sc, why, b in best:
            key = (b["_name"].lower(), b.get("issue_date"), b["_role"])
            if key in seen:
                continue
            seen.add(key)
            hits.append(
                {
                    "score": f"{sc:.2f}",
                    "match_type": why,
                    "crime_name": c["_name"],
                    "crime_age": c.get("Age / Birth Year") or "",
                    "crime_address": c.get("Last Known Address in Kowel") or "",
                    "crime_charge": c.get("Legal Charge in English") or "",
                    "crime_issue_date": c.get("issue_date") or "",
                    "crime_url": c.get("source_url") or "",
                    "register_name": b["_name"],
                    "register_role": b["_role"],
                    "register_firm": b.get("firm_name") or "",
                    "register_business": b.get("business_type") or "",
                    "register_street": b.get("owner_street") or b.get("firm_street") or "",
                    "register_issue_date": b.get("issue_date") or "",
                    "register_url": b.get("source_url") or "",
                }
            )

    fields = list(hits[0].keys()) if hits else [
        "score", "match_type", "crime_name", "register_name"
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(hits)

    people = sorted({h["crime_name"] for h in hits})
    print(f"Crime names: {len(crime)}  Register person/firm strings: {len(register)}")
    print(f"Overlap rows: {len(hits)}  distinct crime names: {len(people)}")
    print(f"Wrote {out_path}")
    for h in hits:
        print(
            f"{h['score']} {h['match_type']:28} | {h['crime_name']:28} | "
            f"{h['register_role']:10} {h['register_name']:28} | "
            f"{h['register_business'][:40]} | crime {h['crime_issue_date']} / reg {h['register_issue_date']}"
        )


if __name__ == "__main__":
    main()
