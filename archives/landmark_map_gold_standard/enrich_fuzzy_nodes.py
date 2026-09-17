#!/usr/bin/env python3
"""Join nodes.csv landmark markers to landmarks_transcribed.csv.

Marker labels are the human annotator's reading of circled codes on the
1939 hand-drawn Kowel map. '(?)' is annotator uncertainty, not OCR.
Numeric street/direction codes may appear twice (both ends of a street).
Named buildings should appear once; extra copies are reassigned using
geography, unused legend slots, and handwriting confusions.

The transcribed legend has no E-series: I1–I3 sit between D9 and F1 and
are the Polish-school block that the English map legend labels E1–E3.
"""

from __future__ import annotations

import csv
import math
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
NODES_PATH = HERE / "nodes.csv"
LANDMARKS_PATH = HERE / "landmarks_transcribed.csv"
OUT_PATH = HERE / "fuzzy_nodes.csv"

# Codes that may legitimately appear more than once on the drawing.
REPEATABLE_CODES = set()
for n in range(1, 70):
    REPEATABLE_CODES.add(str(n))
REPEATABLE_CODES.update({"K2", "K3", "M5", "N1"})

# Map-circle E-series → transcribed I-series (Polish schools).
E_TO_I = {"E1": "I1", "E2": "I2", "E3": "I3"}

# English-only I-block on this drawing (not in landmarks_transcribed.csv).
ENGLISH_I = {
    "I1": "First action (Brest survivors) — English legend only, not in landmarks_transcribed.csv",
    "I2": "Tunnel for pedestrians and vehicles — English legend only, not in landmarks_transcribed.csv",
    "I3": "Passenger tunnel — English legend only, not in landmarks_transcribed.csv",
    "I4": "Stock exchange — English legend only, not in landmarks_transcribed.csv",
}

# node Id → override. Applied before generic rules. landmark_id "" = leave unmatched.
# alternatives: list of legend ids (not including the chosen one).
OVERRIDES = {
    219: {
        "landmark_id": "15",
        "method": "typo_fix",
        "confidence": 0.95,
        "notes": "market_15 is a typo for marker_15; SW pair with 14 (mass grave at new cemetery), direction to Lutsk",
    },
    319: {
        "landmark_id": "68",
        "method": "spatial_unused",
        "confidence": 0.85,
        "notes": "annotator marked (?); far-north road matches 68 (mass grave at Bachów, north of Kowel)",
    },
    318: {
        "landmark_id": "69",
        "method": "street_repeat",
        "confidence": 0.92,
        "notes": "NW exit of the map; 69 is direction to Brest",
    },
    232: {
        "landmark_id": "61",
        "method": "spatial_unused",
        "confidence": 0.70,
        "alternatives": ["58"],
        "notes": "second 69; 69=to Brest belongs on the NW road (node 318). This copy sits in the NE kierunek cluster (62–65); unused 61 Szeroka is east of Kowel",
    },
    234: {
        "landmark_id": "D4",
        "method": "exact_unique",
        "confidence": 0.95,
        "notes": "northern railway; passenger station",
    },
    284: {
        "landmark_id": "D6",
        "method": "spatial_unused",
        "confidence": 0.62,
        "alternatives": ["D9", "D2"],
        "notes": "second D4 rejected (not on the railway). Unused D6 Jewish hospital in west-central town",
    },
    375: {
        "landmark_id": "A9",
        "method": "confusable",
        "confidence": 0.78,
        "alternatives": ["A10"],
        "notes": "A18 not in legend; sits in the Great Synagogue cluster (A1/A7/A8). A9 tailors' synagogue was adjacent to the Great Synagogue",
    },
    326: {
        "landmark_id": "A4",
        "method": "spatial_unused",
        "confidence": 0.72,
        "alternatives": ["A10"],
        "notes": "A(?) west of old town near A3 (Turijsk rabbi) and ul. Brzeska (4); A4 is the Trisk shtibl, related to Turijsk",
    },
    374: {
        "landmark_id": "A5",
        "method": "exact_unique",
        "confidence": 0.88,
        "notes": "A5 Ruzhin shtibl; this copy is next to ul. Magistracka (34), matching the historical address",
    },
    340: {
        "landmark_id": "A6",
        "method": "spatial_unused",
        "confidence": 0.65,
        "alternatives": ["A10"],
        "notes": "second A5; this copy is toward the rynek / new-town side. A6 Prozhansky was in the new city off Warszawska",
    },
    366: {
        "landmark_id": "C5",
        "method": "exact_unique",
        "confidence": 0.86,
        "notes": "far west edge of town; ancient cemetery belongs at the edge",
    },
    299: {
        "landmark_id": "C7",
        "method": "spatial_unused",
        "confidence": 0.74,
        "alternatives": ["C6"],
        "notes": "second C5 sits beside A2 Piaski synagogue and L4 (Piaski ghetto centre); mikvah C7 belongs next to a synagogue, not a cemetery in the street grid",
    },
    378: {
        "landmark_id": "C4",
        "method": "spatial_unused",
        "confidence": 0.68,
        "alternatives": ["C3"],
        "notes": "?C? on the south edge next to F4 Christian cemetery and F5 priests; unused C4 old Jewish cemetery. Alternative: C3 hostel next to C2 old-age home",
    },
    273: {
        "landmark_id": "F2",
        "method": "exact_unique",
        "confidence": 0.80,
        "notes": "Orthodox church in east-central town; F1 Russian church is already placed in old town next to the Great Synagogue",
    },
    334: {
        "landmark_id": "F3",
        "method": "spatial_unused",
        "confidence": 0.70,
        "alternatives": ["F2"],
        "notes": "second F2 in the south civic/Christian cluster (G3 post, F5 priests, F4 cemetery); unused F3 Catholic church",
    },
    275: {
        "landmark_id": "H1",
        "method": "exact_unique",
        "confidence": 0.90,
        "notes": "Kino Oaza; annotator was sure on this copy",
    },
    357: {
        "landmark_id": "H3",
        "method": "spatial_unused",
        "confidence": 0.70,
        "alternatives": ["H1"],
        "notes": "H1(?) duplicate of Oasis; unused H3 Polish night club Zasób (two buildings)",
    },
    347: {
        "landmark_id": "J1",
        "method": "exact_unique",
        "confidence": 0.93,
        "notes": "rynek cluster with H2, H4, M6 (cinemas + Friedrichson pharmacy)",
    },
    381: {
        "landmark_id": "J3",
        "method": "spatial_unused",
        "confidence": 0.72,
        "alternatives": ["J1"],
        "notes": "second J1 just NE of the rynek; unused J3 is the large weekly market",
    },
    291: {
        "landmark_id": "K2",
        "method": "street_repeat",
        "confidence": 0.85,
        "notes": "fields at the western edge",
    },
    367: {
        "landmark_id": "K1",
        "method": "spatial_unused",
        "confidence": 0.70,
        "alternatives": ["K6"],
        "notes": "second K2 sits in town, not in fields; unused K1 city garden",
    },
    268: {
        "landmark_id": "K6",
        "method": "confusable",
        "confidence": 0.60,
        "alternatives": ["K1"],
        "notes": "K8 not in legend (K stops at K7); east of mill M1; unused K6 park and promenade",
    },
    227: {
        "landmark_id": "D9",
        "method": "confusable",
        "confidence": 0.58,
        "alternatives": ["D6", "D8"],
        "notes": "DB not in legend; next to D5 freight yard and ghetto Piaski. Unused D9 Hehalutz HQ",
    },
    304: {
        "landmark_id": "N5",
        "method": "confusable",
        "confidence": 0.55,
        "alternatives": ["N1", "N7", "N6"],
        "notes": "N8 not in legend (N stops at N7); in Piaski near A2 synagogue. Unused N5 house with Star of David",
    },
    228: {
        "landmark_id": "N6",
        "method": "confusable",
        "confidence": 0.52,
        "alternatives": ["N7", "N4", "N1"],
        "notes": "N8 not in legend; east near A11 Entina synagogue (building still exists). Unused N6 Jewish house, now civil registry",
    },
    274: {
        "landmark_id": "54",
        "method": "confusable",
        "confidence": 0.75,
        "notes": "S4: S/5 confusion with ul. Zamoyskiego (54), already labeled at the eastern end (node 255)",
    },
    293: {
        "landmark_id": "J5",
        "method": "confusable",
        "confidence": 0.76,
        "alternatives": ["L6"],
        "notes": "Z4(?): Z/J and 4/5 confusion. Unused J5 tent field sits in the north near J4 soldiers' football field and 23 Pieski",
    },
    224: {
        "landmark_id": "M3",
        "method": "exact_unique",
        "confidence": 0.88,
        "notes": "new electric station in NE Piaski / industrial area",
    },
    363: {
        "landmark_id": "N2",
        "method": "confusable",
        "confidence": 0.60,
        "alternatives": ["M3", "N4", "N6"],
        "notes": "second M3 in a civic/residential cluster next to N3 Gitlis; M/N confusion. Unused N2 teacher's house",
    },
    302: {
        "landmark_id": "I1",
        "method": "letter_shift",
        "confidence": 0.90,
        "notes": "map E-series is transcribed I-series (Polish schools). E1 next to L4 education ministry; I1 high school still exists",
    },
    272: {
        "landmark_id": "I2",
        "method": "letter_shift",
        "confidence": 0.82,
        "notes": "E2 → transcribed I2, Polish national school named after Mościcki",
    },
    303: {
        "landmark_id": "I3",
        "method": "letter_shift",
        "confidence": 0.82,
        "notes": "E3 → transcribed I3, Polish gymnasium named after Pirogow; same education cluster as E1/L4",
    },
    235: {
        "landmark_id": "",
        "method": "unresolved",
        "confidence": 0.0,
        "notes": ENGLISH_I["I3"] + "; marker sits on the railway next to D4 station (transcribed I3 already assigned from E3)",
    },
    377: {
        "landmark_id": "",
        "method": "unresolved",
        "confidence": 0.0,
        "notes": ENGLISH_I["I2"] + "; marker sits near the station (transcribed I2 already assigned from E2)",
    },
    352: {
        "landmark_id": "",
        "method": "unresolved",
        "confidence": 0.0,
        "notes": ENGLISH_I["I4"] + "; marker sits in the town centre",
    },
    306: {
        "landmark_id": "L6",
        "method": "spatial_unused",
        "confidence": 0.58,
        "alternatives": ["B5", "D2"],
        "notes": "illegible; same latitude as L5 Ziskind/SS (y≈366). Unused L6 local KC headquarters",
    },
    364: {
        "landmark_id": "N4",
        "method": "spatial_unused",
        "confidence": 0.48,
        "alternatives": ["B4", "K4", "54"],
        "notes": "??4 last digit 4, east-central near F2/H1/N3. Unused N4 Jewish house (now city museum) matches the 4",
    },
    298: {
        "landmark_id": "B2",
        "method": "exact_unique",
        "confidence": 0.85,
        "notes": "Calomel Jewish school in Piaski, next to A2 Piaski synagogue and L4 ghetto centre",
    },
    336: {
        "landmark_id": "B5",
        "method": "spatial_unused",
        "confidence": 0.68,
        "alternatives": ["B4", "B2"],
        "notes": "second B2 in the south education/welfare cluster (B6 kindergarten, C1 TOZ orphanage). Unused B5 Klara Ehrlich gymnasium (still exists)",
    },
    365: {
        "landmark_id": "A10",
        "method": "spatial_unused",
        "confidence": 0.50,
        "alternatives": ["C4", "B2"],
        "notes": "third B2 at the far west edge next to A3 and C5, near ul. Brzeska (4). Unlikely a school; unused A10 Brzeska synagogue",
    },
    288: {
        "landmark_id": "B3",
        "method": "exact_unique",
        "confidence": 0.72,
        "alternatives": ["B4"],
        "notes": "Tarbut (old) on the old-town / river side near K7 Warsaw bridge",
    },
    271: {
        "landmark_id": "B4",
        "method": "spatial_unused",
        "confidence": 0.70,
        "alternatives": ["B3"],
        "notes": "second B3 in the east/new city near A11 Entina; unused B4 is Tarbut (new)",
    },
    351: {
        "landmark_id": "B1",
        "method": "exact_unique",
        "confidence": 0.80,
        "notes": "Herzlija school / Judenrat; more central, near the rynek",
    },
    337: {
        "landmark_id": "C6",
        "method": "spatial_unused",
        "confidence": 0.50,
        "alternatives": ["B1"],
        "notes": "second B1 in the south welfare cluster (C1 orphanage, B6 kindergarten); unused C6 public bath. Could still be B1",
    },
    283: {
        "landmark_id": "D3",
        "method": "exact_unique",
        "confidence": 0.82,
        "notes": "Makabi/Haszmonia stadium: open land on the west near K5 beach / river",
    },
    269: {
        "landmark_id": "D2",
        "method": "spatial_unused",
        "confidence": 0.64,
        "alternatives": ["D3"],
        "notes": "second D3 in the east near D1 Hashomer Hatzair; unused D2 is Beitar and Bund HQ (youth-org cluster)",
    },
}


def load_landmarks(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8", newline="") as f:
        return {row["id"]: row["name"] for row in csv.DictReader(f)}


def load_nodes(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def parse_marker_label(label: str) -> tuple[str | None, bool, bool]:
    """Return (raw_code, annotator_uncertain, is_typo_market)."""
    label = (label or "").strip()
    if label.startswith("Node "):
        return None, False, False
    m = re.match(r"^marke(r|t)_(.+)$", label)
    if not m:
        return None, False, False
    is_market_typo = m.group(1) == "t"
    code = m.group(2).strip()
    uncertain = bool(
        "(?)" in code
        or "illegible" in code.lower()
        or "??" in code
        or code.startswith("?")
        or code.endswith("?")
    )
    return code, uncertain, is_market_typo


def normalize_code(raw_code: str | None) -> str | None:
    if raw_code is None:
        return None
    code = raw_code.strip()
    if code.lower() in {"(illegible)", "illegible"}:
        return "illegible"
    code = code.replace("(?)", "").replace("(", "").replace(")", "").strip()
    if code == "?C?":
        return "?C?"
    if code.startswith("?"):
        return code
    return code or None


def landmark_kind(lid: str, name: str) -> str:
    if not lid:
        return ""
    n = name or ""
    if n.startswith("ul."):
        return "street"
    if (
        n.startswith("Kierunek")
        or n.startswith("W stronę")
        or n.startswith("Do ")
        or n.startswith("Droga do")
    ):
        return "direction"
    if n.startswith("Rzeka"):
        return "water"
    if n.startswith("Getto") or n.startswith("Obwód") or n.startswith("Stare Miasto"):
        return "district"
    if re.fullmatch(r"\d+", lid):
        return "street"
    return "building"


def format_alt(ids: list[str], landmarks: dict[str, str]) -> str:
    parts = []
    for i in ids:
        if i in landmarks:
            parts.append(f"{i}:{landmarks[i]}")
        else:
            parts.append(i)
    return "; ".join(parts)


def nearest_marker_id(x: float, y: float, markers: list[dict]) -> str:
    best_id = ""
    best_d = float("inf")
    for m in markers:
        d = math.hypot(m["x"] - x, m["y"] - y)
        if d < best_d:
            best_d = d
            best_id = m["id"]
    return best_id


def enrich(nodes: list[dict], landmarks: dict[str, str]) -> list[dict]:
    parsed = []
    for row in nodes:
        raw_code, uncertain, is_market_typo = parse_marker_label(row["Label"])
        code = normalize_code(raw_code)
        kind = "marker" if raw_code is not None else "intersection"
        parsed.append(
            {
                "row": row,
                "node_kind": kind,
                "raw_code": raw_code or "",
                "code": code,
                "uncertain": uncertain,
                "is_market_typo": is_market_typo,
                "x": float(row["x"]),
                "y": float(row["y"]),
                "id": int(row["Id"]),
            }
        )

    markers = [p for p in parsed if p["node_kind"] == "marker"]

    assigned: dict[int, dict] = {}
    used_unique: set[str] = set()

    def consume(lid: str, repeatable: bool) -> None:
        if lid and not repeatable and lid not in REPEATABLE_CODES:
            used_unique.add(lid)

    # Pass 1: explicit overrides.
    for p in markers:
        ov = OVERRIDES.get(p["id"])
        if not ov:
            continue
        lid = ov.get("landmark_id", "")
        name = landmarks.get(lid, "") if lid else ""
        assigned[p["id"]] = {
            "landmark_id": lid,
            "landmark_name": name,
            "match_method": ov["method"],
            "confidence": ov["confidence"],
            "alternatives": format_alt(ov.get("alternatives", []), landmarks),
            "notes": ov["notes"],
        }
        consume(lid, lid in REPEATABLE_CODES)

    # Pass 2: generic assignment for remaining markers.
    # Count in-legend codes among still-unassigned markers (plus already assigned).
    remaining = [p for p in markers if p["id"] not in assigned]
    code_counts: dict[str, int] = {}
    for p in markers:
        c = p["code"]
        if not c:
            continue
        # Count original parsed codes (after normalize).
        code_counts[c] = code_counts.get(c, 0) + 1

    for p in remaining:
        code = p["code"]
        notes = []
        if p["is_market_typo"]:
            notes.append("market_ prefix treated as marker_")
        if p["uncertain"]:
            notes.append("annotator marked as uncertain")

        # Letter-shift E→I if not overridden (should all be overridden).
        if code in E_TO_I:
            lid = E_TO_I[code]
            assigned[p["id"]] = {
                "landmark_id": lid,
                "landmark_name": landmarks.get(lid, ""),
                "match_method": "letter_shift",
                "confidence": 0.80,
                "alternatives": "",
                "notes": f"map {code} is transcribed {lid} (Polish-school block); "
                + "; ".join(notes),
            }
            consume(lid, False)
            continue

        if code in ENGLISH_I and code in landmarks:
            # Map I2/I3 look like transcribed school ids but are the English I-block.
            # Leave unmatched if a school id is already consumed.
            if code in used_unique:
                assigned[p["id"]] = {
                    "landmark_id": "",
                    "landmark_name": "",
                    "match_method": "unresolved",
                    "confidence": 0.0,
                    "alternatives": format_alt([code], landmarks),
                    "notes": ENGLISH_I[code],
                }
                continue

        if code in landmarks:
            ncopies = code_counts.get(code, 1)
            repeatable = code in REPEATABLE_CODES
            if repeatable:
                method = "street_repeat" if ncopies > 1 else "exact_unique"
                conf = 0.85 if ncopies > 1 else 0.95
                if p["uncertain"]:
                    conf = min(conf, 0.80)
                assigned[p["id"]] = {
                    "landmark_id": code,
                    "landmark_name": landmarks[code],
                    "match_method": method,
                    "confidence": conf,
                    "alternatives": "",
                    "notes": "; ".join(notes),
                }
                consume(code, True)
            elif ncopies == 1 and code not in used_unique:
                assigned[p["id"]] = {
                    "landmark_id": code,
                    "landmark_name": landmarks[code],
                    "match_method": "exact_unique",
                    "confidence": 0.95 if not p["uncertain"] else 0.80,
                    "alternatives": "",
                    "notes": "; ".join(notes),
                }
                consume(code, False)
            elif code not in used_unique:
                # Unique building, first remaining copy wins.
                assigned[p["id"]] = {
                    "landmark_id": code,
                    "landmark_name": landmarks[code],
                    "match_method": "exact_unique",
                    "confidence": 0.80,
                    "alternatives": "",
                    "notes": ("; ".join(notes + [f"one of {ncopies} copies of {code}; first assigned"])),
                }
                consume(code, False)
            else:
                assigned[p["id"]] = {
                    "landmark_id": "",
                    "landmark_name": "",
                    "match_method": "unresolved",
                    "confidence": 0.0,
                    "alternatives": format_alt([code], landmarks),
                    "notes": "; ".join(
                        notes + [f"duplicate unique-building code {code} already assigned"]
                    ),
                }
            continue

        # Not in legend.
        assigned[p["id"]] = {
            "landmark_id": "",
            "landmark_name": "",
            "match_method": "unresolved",
            "confidence": 0.0,
            "alternatives": "",
            "notes": "; ".join(notes + [f"code {code!r} is not in landmarks_transcribed.csv"]),
        }

    # Nearest marker for intersections.
    marker_pts = [
        {"id": str(p["id"]), "x": p["x"], "y": p["y"]} for p in markers
    ]

    out = []
    for p in parsed:
        row = p["row"]
        rec = {
            "Id": row["Id"],
            "Label": row["Label"],
            "x": row["x"],
            "y": row["y"],
            "pixel_x": row["pixel_x"],
            "pixel_y": row["pixel_y"],
            "node_kind": p["node_kind"],
            "raw_code": p["raw_code"],
            "annotator_uncertain": "true" if p["uncertain"] else "false",
            "landmark_id": "",
            "landmark_name": "",
            "landmark_kind": "",
            "match_method": "",
            "confidence": "",
            "alternatives": "",
            "notes": "",
            "nearest_marker_id": "",
        }
        if p["node_kind"] == "marker":
            a = assigned[p["id"]]
            rec.update(
                {
                    "landmark_id": a["landmark_id"],
                    "landmark_name": a["landmark_name"],
                    "landmark_kind": landmark_kind(a["landmark_id"], a["landmark_name"]),
                    "match_method": a["match_method"],
                    "confidence": f"{a['confidence']:.2f}",
                    "alternatives": a["alternatives"],
                    "notes": a["notes"],
                }
            )
        else:
            rec["nearest_marker_id"] = nearest_marker_id(p["x"], p["y"], marker_pts)
        out.append(rec)
    return out


def audit(rows: list[dict], landmarks: dict[str, str]) -> None:
    markers = [r for r in rows if r["node_kind"] == "marker"]
    intersections = [r for r in rows if r["node_kind"] == "intersection"]
    print(f"nodes={len(rows)} markers={len(markers)} intersections={len(intersections)}")

    matched = [r for r in markers if r["landmark_id"]]
    unresolved = [r for r in markers if not r["landmark_id"]]
    uncertain = [r for r in markers if r["annotator_uncertain"] == "true"]
    print(f"matched={len(matched)} unresolved={len(unresolved)} annotator_uncertain={len(uncertain)}")

    print("\n--- unresolved markers ---")
    for r in unresolved:
        print(f"  id={r['Id']:4s} {r['Label']:22s} method={r['match_method']:16s} {r['notes'][:110]}")

    print("\n--- uncertain markers ---")
    for r in uncertain:
        print(
            f"  id={r['Id']:4s} {r['Label']:22s} → {r['landmark_id'] or '(none)':6s} "
            f"conf={r['confidence']} {r['notes'][:90]}"
        )

    used = [r["landmark_id"] for r in markers if r["landmark_id"]]
    unused = [i for i in landmarks if i not in used]
    print(f"\n--- unused legend ids ({len(unused)}) ---")
    print(", ".join(unused))

    from collections import Counter

    c = Counter(used)
    print("\n--- chosen ids used more than once ---")
    for lid, n in sorted(c.items(), key=lambda kv: (-kv[1], kv[0])):
        if n < 2:
            continue
        kind = next(r["landmark_kind"] for r in markers if r["landmark_id"] == lid)
        print(f"  {lid:6s} x{n}  ({kind})  {landmarks[lid]}")

    print("\n--- unique-building ids used more than once (should be empty) ---")
    bad = False
    for lid, n in c.items():
        if n > 1 and lid not in REPEATABLE_CODES:
            bad = True
            print(f"  CONFLICT {lid} x{n}  {landmarks.get(lid)}")
    if not bad:
        print("  none")

    # Names must come from the transcribed file.
    extra = [r for r in markers if r["landmark_name"] and r["landmark_id"] not in landmarks]
    print(f"\nnames not in transcribed file: {len(extra)}")

    print("\n--- override / special assignments ---")
    for r in markers:
        if r["match_method"] in {
            "typo_fix",
            "letter_shift",
            "confusable",
            "spatial_unused",
        } or r["Id"] in {str(i) for i in OVERRIDES}:
            print(
                f"  id={r['Id']:4s} {r['Label']:22s} → {r['landmark_id'] or '(none)':6s} "
                f"{r['match_method']:16s} conf={r['confidence']}"
            )


def main() -> None:
    landmarks = load_landmarks(LANDMARKS_PATH)
    nodes = load_nodes(NODES_PATH)
    rows = enrich(nodes, landmarks)

    fieldnames = [
        "Id",
        "Label",
        "x",
        "y",
        "pixel_x",
        "pixel_y",
        "node_kind",
        "raw_code",
        "annotator_uncertain",
        "landmark_id",
        "landmark_name",
        "landmark_kind",
        "match_method",
        "confidence",
        "alternatives",
        "notes",
        "nearest_marker_id",
    ]
    with OUT_PATH.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    print(f"wrote {OUT_PATH} ({len(rows)} rows)")
    audit(rows, landmarks)


if __name__ == "__main__":
    main()
