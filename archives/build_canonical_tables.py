#!/usr/bin/env python3
"""Build ID'd canonical CSVs under archives/normalized/ from existing extracts.

Does not invent identities: people cluster only when given name + surname +
birth year all match. Buildings cluster on a folded display name after a small
alias list. Streets take stable ids from the truth table.

Regenerate: python archives/build_canonical_tables.py
"""

from __future__ import annotations

import csv
import hashlib
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "archives" / "normalized"
CRIME = ROOT / "archives" / "database of kowel crime" / "data"
TRUTH = OUT / "kowel_streets_truth_table.csv"

DIACRITIC = str.maketrans(
    {
        "ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n", "ó": "o",
        "ś": "s", "ź": "z", "ż": "z",
        "Ą": "A", "Ć": "C", "Ę": "E", "Ł": "L", "Ń": "N", "Ó": "O",
        "Ś": "S", "Ź": "Z", "Ż": "Z",
    }
)

BUILDING_ALIAS = {
    "great synagogue": "wielka synagoga",
    "wielka synagoga": "wielka synagoga",
    "synagogue piaski": "synagoga piaski",
    "synagoga piaski": "synagoga piaski",
    "jewish hospital": "szpital zydowski",
    "szpital zydowski": "szpital zydowski",
    "train station": "dworzec",
    "dworzec": "dworzec",
    "armarnik s mill": "mlyn armarnika",
    "mlyn armarnika": "mlyn armarnika",
}

HOUSE_RE = re.compile(
    r"(?P<street>.*?)(?:\s+(?P<num>\d+[A-Za-z]?(?:/\S+)?))?\s*$"
)
YEAR_RE = re.compile(r"\b((?:18|19|20)\d{2})\b")
BLANK = {"", "-", "—", "none", "nan", "not specified"}


def fold(s: str) -> str:
    s = (s or "").strip().lower().translate(DIACRITIC)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(
        r"^(ul\.?|ulica|al\.?|aleja|pl\.?|plac|vul\.?|vulytsia)\s+",
        "",
        s,
    )
    s = re.sub(r"[^a-z0-9\s\-]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def sid(kind: str, *parts: str) -> str:
    raw = kind + ":" + "|".join(parts)
    return kind + ":" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def clean(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def nonempty(s: str | None) -> bool:
    return fold(s or "") not in BLANK and clean(s or "") not in {"", "-"}


def _cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, list):
        return ", ".join(str(x).strip() for x in v if x is not None)
    return str(v).strip()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        print(f"  skip missing {path.relative_to(ROOT)}")
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return [{(k or ""): _cell(v) for k, v in row.items()} for row in csv.DictReader(f)]


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fields})
    print(f"Wrote {len(rows):5d}  {path.relative_to(ROOT)}")


def year_of(*vals: str) -> str:
    for v in vals:
        m = YEAR_RE.search(v or "")
        if m:
            return m.group(1)
    return ""


def split_house(addr: str) -> tuple[str, str]:
    addr = clean(addr)
    if not addr:
        return "", ""
    addr = re.sub(r"^(ul\.?|ulica|przy ul\.?)\s+", "", addr, flags=re.I)
    m = HOUSE_RE.match(addr)
    if not m:
        return addr, ""
    return clean(m.group("street") or addr), clean(m.group("num") or "")


class Streets:
    def __init__(self, rows: list[dict[str, str]]):
        self.rows = []
        self.by_fold: list[tuple[str, str, str]] = []
        for r in rows:
            name = r["street_name"]
            street_id = sid("st", fold(name) or name)
            corridor = r.get("same_as") or street_id
            out = {
                "street_id": street_id,
                "corridor_id": corridor,
                **r,
            }
            self.rows.append(out)
            fn = fold(name)
            if fn:
                self.by_fold.append((fn, street_id, name))
        self.by_fold.sort(key=lambda t: -len(t[0]))

    def match(self, raw: str) -> tuple[str, str]:
        street, _num = split_house(raw)
        token = fold(street) or fold(raw)
        if len(token) < 3 or token in {
            "kowel", "kovel", "kowlu", "kowla", "wolyn", "volyn",
            "poland", "polska", "ukraine", "unknown",
        }:
            return "", ""
        exact = [(fn, i, n) for fn, i, n in self.by_fold if fn == token]
        if len(exact) == 1:
            return exact[0][1], exact[0][2]
        prefix = [
            (fn, i, n)
            for fn, i, n in self.by_fold
            if len(fn) >= 4 and (token.startswith(fn) or fn.startswith(token))
        ]
        if prefix:
            prefix.sort(key=lambda t: -len(t[0]))
            return prefix[0][1], prefix[0][2]
        return "", ""


def load_streets() -> Streets:
    rows = read_csv(TRUTH)
    if not rows:
        raise SystemExit(f"missing {TRUTH}")
    return Streets(rows)


def parse_doctor_name(raw: str) -> tuple[str, str]:
    raw = raw.strip().strip('"')
    if "," in raw:
        last, given = raw.split(",", 1)
        return clean(given), clean(last)
    return "", clean(raw)


def parse_crime_name(raw: str) -> tuple[str, str]:
    parts = clean(raw).split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return "", parts[0]
    return " ".join(parts[1:]), parts[0]


def cluster_person(given: str, surname: str, birth_year: str) -> str | None:
    g, s, y = fold(given), fold(surname), clean(birth_year)
    if g and s and y:
        return f"{g}|{s}|{y}"
    return None


def collect_people(streets: Streets) -> tuple[list[dict], list[dict]]:
    sources: list[dict] = []

    def add(
        source_file: str,
        source_key: str,
        given: str,
        surname: str,
        **extra: str,
    ) -> None:
        given, surname = clean(given), clean(surname)
        if not nonempty(given) and not nonempty(surname):
            return
        addr = extra.get("address_raw", "")
        street_id, street_name = streets.match(
            extra.get("street_hint") or addr
        )
        byear = extra.get("birth_year") or year_of(
            extra.get("birth_date", ""), extra.get("notes", "")
        )
        sources.append(
            {
                "source_row_id": sid("src", source_file, source_key, given, surname, str(len(sources))),
                "source_file": source_file,
                "source_key": source_key,
                "given_name": given,
                "surname": surname,
                "maiden_name": extra.get("maiden_name", ""),
                "birth_date": extra.get("birth_date", ""),
                "birth_year": byear,
                "birth_place": extra.get("birth_place", ""),
                "death_date": extra.get("death_date", ""),
                "father": extra.get("father", ""),
                "mother": extra.get("mother", ""),
                "address_raw": addr,
                "street_id": street_id,
                "street_name": street_name,
                "source_url": extra.get("source_url", ""),
                "notes": extra.get("notes", "")[:400],
                "_cluster": cluster_person(given, surname, byear),
            }
        )

    for i, r in enumerate(read_csv(ROOT / "archives" / "people_living_in_Kowel.csv")):
        add(
            "archives/people_living_in_Kowel.csv",
            str(i),
            r.get("Imię", ""),
            r.get("Nazwisko", ""),
            maiden_name=r.get("Nazwisko panieńskie", ""),
            birth_date=r.get("Data urodzenia", ""),
            birth_place=r.get("Miejsce urodzenia", ""),
            father=r.get("Imię ojca", ""),
            mother=r.get("Imię matki", ""),
            death_date=r.get("Data śmierci", ""),
        )

    for i, r in enumerate(read_csv(OUT / "people_and_birth_places.csv")):
        notes = r.get("notes", "")
        add(
            "archives/normalized/people_and_birth_places.csv",
            str(i),
            r.get("first_name", ""),
            r.get("last_name", ""),
            birth_place=r.get("birth_place", ""),
            address_raw=r.get("place_of_residence", ""),
            notes=notes,
            birth_year=year_of(notes),
        )

    births = read_csv(ROOT / "archives" / "kowel_births.csv")
    births_alt = read_csv(ROOT / "archives" / "kowel_births_1843_1945.csv")
    skip_alt = births_alt and [tuple(r.items()) for r in births] == [
        tuple(r.items()) for r in births_alt
    ]
    for i, r in enumerate(births):
        add(
            "archives/kowel_births.csv",
            r.get("Signature", str(i)),
            r.get("First Name", ""),
            r.get("Last Name", ""),
            maiden_name=r.get("Maiden Name", ""),
            birth_date=r.get("Date of Birth", ""),
            birth_place=r.get("Place of Birth", ""),
            father=r.get("Father (adoptive father)", ""),
            mother=r.get("Mother (adoptive mother)", ""),
            death_date=r.get("Date of decease", ""),
            address_raw=" ".join(
                filter(
                    None,
                    [
                        r.get("Last residence (Street)", ""),
                        r.get("Last residence (House number)", ""),
                        r.get("Last residence (Town)", ""),
                    ],
                )
            ),
            notes=r.get("Prisoner #", ""),
        )
    if not skip_alt:
        for i, r in enumerate(births_alt):
            add(
                "archives/kowel_births_1843_1945.csv",
                r.get("Signature", str(i)),
                r.get("First Name", ""),
                r.get("Last Name", ""),
                birth_date=r.get("Date of Birth", ""),
                birth_place=r.get("Place of Birth", ""),
            )

    for i, r in enumerate(read_csv(ROOT / "archives" / "Auschwitz_prisoners_born_in_kowel.csv")):
        add(
            "archives/Auschwitz_prisoners_born_in_kowel.csv",
            str(i),
            "",
            r.get("surname", ""),
            birth_year=r.get("birth_year", ""),
            birth_place=r.get("birthplace", ""),
        )

    for i, r in enumerate(read_csv(ROOT / "archives" / "kowel_born_deported_east.csv")):
        add(
            "archives/kowel_born_deported_east.csv",
            str(i),
            r.get("Imię", ""),
            r.get("Nazwisko", ""),
            father=r.get("Imię ojca", ""),
            birth_year=r.get("Rok urodzenia", ""),
            notes=r.get("Symbol zestawienia", ""),
        )

    for i, r in enumerate(read_csv(ROOT / "archives" / "polish_military_born_in_kowel.csv")):
        add(
            "archives/polish_military_born_in_kowel.csv",
            r.get("Sygnatura", str(i)),
            r.get("Imię", ""),
            r.get("Nazwisko", ""),
            father=r.get("Imię ojca", ""),
            birth_date=r.get("Data urodzenia", ""),
            birth_place=r.get("Miejsce urodzenia", ""),
            notes=r.get("Akcje", ""),
        )

    for i, r in enumerate(read_csv(ROOT / "archives" / "ship_passengers_born_in_kowel.csv")):
        add(
            "archives/ship_passengers_born_in_kowel.csv",
            str(i),
            "",
            r.get("Passenger", ""),
            birth_place=r.get("Place of birth", ""),
            notes=f"{r.get('Ship_name', '')} {r.get('Destination', '')} {r.get('Age', '')}",
        )

    for i, r in enumerate(read_csv(ROOT / "kowel_residents_1938.csv")):
        fn, ln = r.get("First Name", ""), r.get("Last Name", "")
        if not nonempty(fn) and not nonempty(ln):
            continue
        if fn in {"-"}:
            fn = ""
        if ln in {"-"}:
            ln = ""
        addr = " ".join(filter(None, [r.get("Street", ""), r.get("Number", "")]))
        add(
            "kowel_residents_1938.csv",
            r.get("Telephone Number", str(i)),
            fn,
            ln,
            address_raw=addr,
            street_hint=r.get("Street", ""),
            notes=r.get("Industry", "") or r.get("Type", ""),
        )

    for i, r in enumerate(read_csv(ROOT / "doctors_resident_in_kowel.csv")):
        given, surname = parse_doctor_name(r.get("surname", ""))
        add(
            "doctors_resident_in_kowel.csv",
            str(i),
            given,
            surname,
            address_raw=" ".join(filter(None, [r.get("street", ""), r.get("number", "")])),
            street_hint=r.get("street", ""),
            notes="doctor 1920",
        )

    groups: dict[str, list[int]] = defaultdict(list)
    uniques: list[int] = []
    for i, row in enumerate(sources):
        key = row["_cluster"]
        if key:
            groups[key].append(i)
        else:
            uniques.append(i)

    people: list[dict] = []
    for key, idxs in sorted(groups.items()):
        pid = sid("p", key)
        members = [sources[i] for i in idxs]
        pick = max(members, key=lambda m: (len(m["given_name"]), len(m["notes"])))
        files = sorted({m["source_file"] for m in members})
        for m in members:
            m["person_id"] = pid
        people.append(
            {
                "person_id": pid,
                "given_name": pick["given_name"],
                "surname": pick["surname"],
                "maiden_name": next((m["maiden_name"] for m in members if m["maiden_name"]), ""),
                "birth_year": pick["birth_year"],
                "birth_place": next((m["birth_place"] for m in members if m["birth_place"]), ""),
                "death_date": next((m["death_date"] for m in members if m["death_date"]), ""),
                "street_id": next((m["street_id"] for m in members if m["street_id"]), ""),
                "source_count": str(len(members)),
                "source_files": ";".join(files),
                "clustered": "y" if len(members) > 1 else "n",
            }
        )

    for i in uniques:
        m = sources[i]
        pid = sid("p", m["source_row_id"])
        m["person_id"] = pid
        people.append(
            {
                "person_id": pid,
                "given_name": m["given_name"],
                "surname": m["surname"],
                "maiden_name": m["maiden_name"],
                "birth_year": m["birth_year"],
                "birth_place": m["birth_place"],
                "death_date": m["death_date"],
                "street_id": m["street_id"],
                "source_count": "1",
                "source_files": m["source_file"],
                "clustered": "n",
            }
        )

    people.sort(key=lambda r: (fold(r["surname"]), fold(r["given_name"]), r["person_id"]))
    for s in sources:
        s.pop("_cluster", None)
    sources.sort(key=lambda r: (r["source_file"], r["surname"], r["given_name"]))
    return people, sources


def collect_buildings(streets: Streets) -> list[dict]:
    raw: list[dict] = []

    def add(name: str, source_file: str, source_key: str, **extra: str) -> None:
        name = clean(name)
        if not nonempty(name):
            return
        if name.lower().startswith(("ul.", "ulica", "aleja", "droga ", "kierunek")):
            return
        addr = extra.get("address_raw", "")
        street_id, street_name = streets.match(extra.get("street_hint") or addr)
        fn = BUILDING_ALIAS.get(fold(name), fold(name))
        distinctive = len(fn) >= 10 or any(
            k in fn
            for k in (
                "synagog", "szpital", "hospital", "dworzec", "station",
                "mlyn", "mill", "beit", "midras", "most", "school", "szkol",
            )
        )
        cluster = fn if distinctive else None
        raw.append(
            {
                "name": name,
                "address_raw": addr,
                "street_id": street_id,
                "street_name": street_name,
                "house_number": extra.get("house_number", "") or split_house(addr)[1],
                "map_node_id": extra.get("map_node_id", ""),
                "lat": extra.get("lat", ""),
                "lon": extra.get("lon", ""),
                "purpose": extra.get("purpose", ""),
                "destroyed": extra.get("destroyed", ""),
                "year_mentioned": extra.get("year_mentioned", ""),
                "source_file": source_file,
                "source_key": source_key,
                "notes": extra.get("notes", "")[:400],
                "_cluster": cluster,
            }
        )

    for i, r in enumerate(read_csv(ROOT / "maps" / "kowel_buildings.csv")):
        dest = r.get("Destroyed (Y/N)", "")
        add(
            r.get("Building", ""),
            "maps/kowel_buildings.csv",
            str(i),
            address_raw=r.get("Address", ""),
            purpose=r.get("Purpose", ""),
            destroyed="y" if dest.upper().startswith("Y") else dest,
        )

    for r in read_csv(ROOT / "maps" / "kowel_landmarks_index.csv"):
        street, num = split_house(r.get("Address", ""))
        add(
            r.get("Polish") or r.get("Description", ""),
            "maps/kowel_landmarks_index.csv",
            r.get("Index", ""),
            address_raw=r.get("Address", ""),
            street_hint=street,
            house_number=num,
            purpose=r.get("Building_Type", ""),
            destroyed="y" if "destroy" in (r.get("Status") or "").lower() else r.get("Status", ""),
            year_mentioned=r.get("Construction_Period", ""),
            notes=r.get("Notes", "") or r.get("Historical_Significance", ""),
        )

    for i, r in enumerate(read_csv(ROOT / "archives" / "known_buildings.csv")):
        add(
            r.get("building_name", ""),
            "archives/known_buildings.csv",
            str(i),
            address_raw=r.get("building_location", ""),
            year_mentioned=r.get("year_mentioned", ""),
            notes=r.get("events_related_to_it", ""),
        )

    for i, r in enumerate(read_csv(ROOT / "archives" / "places_described.csv")):
        if (r.get("location_within_kowel_city_limits") or "").strip().lower() != "yes":
            continue
        add(
            r.get("name", ""),
            "archives/places_described.csv",
            str(i),
            notes=r.get("description", ""),
            year_mentioned=r.get("year_mentioned", ""),
        )

    heb = ROOT / "archives" / "locations_on_hebrew_map_kowel.csv"
    for i, r in enumerate(read_csv(heb)):
        # quoted headers
        name = r.get("Prayer House") or r.get('"Prayer House"') or next(iter(r.values()), "")
        loc = r.get("Location") or r.get('"Location"') or ""
        det = r.get("Details/Sources") or r.get('"Details/Sources"') or ""
        add(
            name,
            "archives/locations_on_hebrew_map_kowel.csv",
            str(i),
            address_raw=loc,
            notes=det,
        )

    for r in read_csv(ROOT / "archives" / "landmark_map_gold_standard" / "fuzzy_nodes.csv"):
        if (r.get("landmark_kind") or "").lower() != "building":
            continue
        add(
            r.get("landmark_name") or r.get("Label", ""),
            "archives/landmark_map_gold_standard/fuzzy_nodes.csv",
            r.get("Id", ""),
            map_node_id=r.get("Id", ""),
            lat=r.get("lat", ""),
            lon=r.get("lon", ""),
            notes=r.get("notes", "") or r.get("match_method", ""),
        )

    groups: dict[str, list[int]] = defaultdict(list)
    uniques: list[int] = []
    for i, row in enumerate(raw):
        if row["_cluster"]:
            groups[row["_cluster"]].append(i)
        else:
            uniques.append(i)

    out: list[dict] = []
    for key, idxs in sorted(groups.items()):
        bid = sid("b", key)
        members = [raw[i] for i in idxs]
        pick = max(members, key=lambda m: (bool(m["lat"]), bool(m["street_id"]), len(m["name"])))
        files = sorted({m["source_file"] for m in members})
        out.append(
            {
                "building_id": bid,
                "name": pick["name"],
                "address_raw": pick["address_raw"],
                "street_id": next((m["street_id"] for m in members if m["street_id"]), ""),
                "street_name": next((m["street_name"] for m in members if m["street_name"]), ""),
                "house_number": next((m["house_number"] for m in members if m["house_number"]), ""),
                "map_node_id": next((m["map_node_id"] for m in members if m["map_node_id"]), ""),
                "lat": next((m["lat"] for m in members if m["lat"]), ""),
                "lon": next((m["lon"] for m in members if m["lon"]), ""),
                "purpose": next((m["purpose"] for m in members if m["purpose"]), ""),
                "destroyed": next((m["destroyed"] for m in members if m["destroyed"]), ""),
                "year_mentioned": next((m["year_mentioned"] for m in members if m["year_mentioned"]), ""),
                "source_count": str(len(members)),
                "source_files": ";".join(files),
                "notes": pick["notes"],
                "clustered": "y" if len(members) > 1 else "n",
            }
        )
    for i in uniques:
        m = raw[i]
        bid = sid("b", m["source_file"], m["source_key"], fold(m["name"]))
        out.append(
            {
                "building_id": bid,
                "name": m["name"],
                "address_raw": m["address_raw"],
                "street_id": m["street_id"],
                "street_name": m["street_name"],
                "house_number": m["house_number"],
                "map_node_id": m["map_node_id"],
                "lat": m["lat"],
                "lon": m["lon"],
                "purpose": m["purpose"],
                "destroyed": m["destroyed"],
                "year_mentioned": m["year_mentioned"],
                "source_count": "1",
                "source_files": m["source_file"],
                "notes": m["notes"],
                "clustered": "n",
            }
        )
    out.sort(key=lambda r: (fold(r["name"]), r["building_id"]))
    return out


def collect_firms(streets: Streets) -> list[dict]:
    rows: list[dict] = []

    def add(name: str, source_file: str, source_key: str, **extra: str) -> None:
        name = clean(name)
        owner = clean(extra.get("owner_name", ""))
        if not nonempty(name) and not nonempty(owner):
            return
        addr = extra.get("address_raw", "")
        hint = extra.get("street_hint") or addr
        street_id, street_name = streets.match(hint)
        _st, num = split_house(hint)
        rows.append(
            {
                "firm_id": sid("f", source_file, source_key, name or owner),
                "name": name,
                "owner_name": owner,
                "business_type": extra.get("business_type", ""),
                "address_raw": addr,
                "street_id": street_id,
                "street_name": street_name,
                "house_number": extra.get("house_number", "") or num,
                "year": extra.get("year", ""),
                "source_file": source_file,
                "source_url": extra.get("source_url", ""),
                "object_id": extra.get("object_id", ""),
            }
        )

    for i, r in enumerate(read_csv(ROOT / "1929_business_directory.csv")):
        add(
            r.get("Name", ""),
            "1929_business_directory.csv",
            str(i),
            address_raw=r.get("Address", ""),
            business_type=r.get("Section", ""),
            year="1929",
        )

    for i, r in enumerate(read_csv(CRIME / "obwieszczenia_publiczne" / "kowel_businesses.csv")):
        add(
            r.get("firm_name", ""),
            "archives/database of kowel crime/data/obwieszczenia_publiczne/kowel_businesses.csv",
            r.get("object_id", str(i)) + str(i),
            owner_name=r.get("owner_name", ""),
            business_type=r.get("business_type", ""),
            address_raw=r.get("firm_street") or r.get("owner_street", ""),
            street_hint=r.get("firm_street") or r.get("owner_street", ""),
            year=(r.get("exists_since") or r.get("issue_date") or "")[:4],
            source_url=r.get("source_url", ""),
            object_id=r.get("object_id", ""),
        )

    for i, r in enumerate(read_csv(ROOT / "archive" / "lucka_businesses.csv")):
        add(
            r.get("business_name", ""),
            "archive/lucka_businesses.csv",
            str(i),
            business_type=r.get("industry", ""),
            street_hint="Łucka",
            address_raw=f"Łucka {r.get('street_number', '')}".strip(),
            house_number=r.get("street_number", ""),
            year="1929",
        )

    for i, r in enumerate(read_csv(ROOT / "kowel_residents_1938.csv")):
        if (r.get("Type") or "").lower() != "business":
            continue
        add(
            r.get("Full Name", ""),
            "kowel_residents_1938.csv",
            r.get("Telephone Number", str(i)),
            business_type=r.get("Industry", ""),
            street_hint=r.get("Street", ""),
            address_raw=" ".join(filter(None, [r.get("Street", ""), r.get("Number", "")])),
            house_number=r.get("Number", ""),
            year="1938",
        )

    rows.sort(key=lambda r: (fold(r["name"] or r["owner_name"]), r["firm_id"]))
    return rows


def collect_crime(streets: Streets, people: list[dict]) -> list[dict]:
    index: dict[str, str] = {}
    by_name: dict[str, list[str]] = defaultdict(list)
    for p in people:
        key = cluster_person(p["given_name"], p["surname"], p["birth_year"])
        if key:
            index[key] = p["person_id"]
        g, s = fold(p["given_name"]), fold(p["surname"])
        if g and s:
            by_name[f"{g}|{s}"].append(p["person_id"])

    out: list[dict] = []
    src = CRIME / "kowel_criminal_database" / "kowel_criminal_database.csv"
    for i, r in enumerate(read_csv(src)):
        given, surname = parse_crime_name(r.get("Name", ""))
        addr = r.get("Last Known Address in Kowel", "")
        street_id, street_name = streets.match(addr)
        byear = year_of(r.get("Age / Birth Year", ""), r.get("excerpt", ""))
        key = cluster_person(given, surname, byear)
        pid = index.get(key or "", "")
        if not pid:
            nk = f"{fold(given)}|{fold(surname)}"
            ids = list(dict.fromkeys(by_name.get(nk, [])))
            if len(ids) == 1:
                pid = ids[0]
        out.append(
            {
                "crime_id": sid("c", r.get("object_id", ""), r.get("Name", ""), str(i)),
                "person_id": pid,
                "name_raw": r.get("Name", ""),
                "given_name": given,
                "surname": surname,
                "age_or_birth": r.get("Age / Birth Year", ""),
                "address_raw": addr,
                "street_id": street_id,
                "street_name": street_name,
                "charge_code": r.get("Penal Code Charge", ""),
                "charge_en": r.get("Legal Charge in English", ""),
                "kowel_link": r.get("kowel_link", ""),
                "object_id": r.get("object_id", ""),
                "issue_date": r.get("issue_date", ""),
                "source_url": r.get("source_url", ""),
                "excerpt": (r.get("excerpt") or "")[:400],
            }
        )
    return out


def annotate_truth(streets: Streets) -> None:
    fields = [
        "street_id",
        "corridor_id",
        "street_name",
        "year_ranges",
        "exists_today",
        "same_as",
        "notes",
        "sources",
    ]
    write_csv(TRUTH, streets.rows, fields)
    doc = OUT / "kowel_streets_truth_table.md"
    text = doc.read_text(encoding="utf-8") if doc.exists() else ""
    if "`street_id`" not in text:
        text = text.replace(
            "- `street_name` — one historical name form per row (Polish preferred)",
            "- `street_id` — stable id (`st:` + hash of folded name)\n"
            "- `corridor_id` — `same_as` corridor when set, else `street_id`\n"
            "- `street_name` — one historical name form per row (Polish preferred)",
        )
        doc.write_text(text, encoding="utf-8")


def main() -> None:
    streets = load_streets()
    annotate_truth(streets)
    write_csv(
        OUT / "streets.csv",
        streets.rows,
        [
            "street_id",
            "corridor_id",
            "street_name",
            "year_ranges",
            "exists_today",
            "same_as",
            "notes",
            "sources",
        ],
    )

    people, people_sources = collect_people(streets)
    write_csv(
        OUT / "people.csv",
        people,
        [
            "person_id",
            "given_name",
            "surname",
            "maiden_name",
            "birth_year",
            "birth_place",
            "death_date",
            "street_id",
            "source_count",
            "source_files",
            "clustered",
        ],
    )
    write_csv(
        OUT / "people_sources.csv",
        people_sources,
        [
            "source_row_id",
            "person_id",
            "source_file",
            "source_key",
            "given_name",
            "surname",
            "maiden_name",
            "birth_date",
            "birth_year",
            "birth_place",
            "death_date",
            "father",
            "mother",
            "address_raw",
            "street_id",
            "street_name",
            "source_url",
            "notes",
        ],
    )

    buildings = collect_buildings(streets)
    write_csv(
        OUT / "buildings.csv",
        buildings,
        [
            "building_id",
            "name",
            "address_raw",
            "street_id",
            "street_name",
            "house_number",
            "map_node_id",
            "lat",
            "lon",
            "purpose",
            "destroyed",
            "year_mentioned",
            "source_count",
            "source_files",
            "notes",
            "clustered",
        ],
    )

    firms = collect_firms(streets)
    write_csv(
        OUT / "firms.csv",
        firms,
        [
            "firm_id",
            "name",
            "owner_name",
            "business_type",
            "address_raw",
            "street_id",
            "street_name",
            "house_number",
            "year",
            "source_file",
            "source_url",
            "object_id",
        ],
    )

    crime = collect_crime(streets, people)
    write_csv(
        OUT / "crime.csv",
        crime,
        [
            "crime_id",
            "person_id",
            "name_raw",
            "given_name",
            "surname",
            "age_or_birth",
            "address_raw",
            "street_id",
            "street_name",
            "charge_code",
            "charge_en",
            "kowel_link",
            "object_id",
            "issue_date",
            "source_url",
            "excerpt",
        ],
    )

    n_street_people = sum(1 for r in people if r["street_id"])
    n_street_firms = sum(1 for r in firms if r["street_id"])
    n_street_crime = sum(1 for r in crime if r["street_id"])
    n_street_bldg = sum(1 for r in buildings if r["street_id"])
    n_geo = sum(1 for r in buildings if r["lat"])
    n_cluster_p = sum(1 for r in people if r["clustered"] == "y")
    n_crime_p = sum(1 for r in crime if r["person_id"])
    print(
        f"streets={len(streets.rows)} people={len(people)} "
        f"(clustered {n_cluster_p}, with street {n_street_people}) "
        f"sources={len(people_sources)} buildings={len(buildings)} "
        f"(street {n_street_bldg}, geo {n_geo}) firms={len(firms)} "
        f"(street {n_street_firms}) crime={len(crime)} "
        f"(street {n_street_crime}, person {n_crime_p})"
    )


if __name__ == "__main__":
    main()
