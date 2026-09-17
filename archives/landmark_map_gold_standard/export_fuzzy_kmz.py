#!/usr/bin/env python3
"""Write fuzzy_nodes.csv + edges.csv as a KMZ for Google Earth overlay."""

from __future__ import annotations

import csv
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
NODES = HERE / "fuzzy_nodes.csv"
EDGES = HERE / "edges.csv"
OUT_KMZ = HERE / "fuzzy_nodes.kmz"
OUT_EDGES = HERE / "fuzzy_edges.csv"

STYLES = {
    "building": ("ff2d2dc8", "http://maps.google.com/mapfiles/kml/paddle/red-circle.png", 1.1),
    "street": ("ff00d4ff", "http://maps.google.com/mapfiles/kml/paddle/ylw-circle.png", 0.95),
    "direction": ("ff4caf50", "http://maps.google.com/mapfiles/kml/paddle/grn-circle.png", 0.95),
    "district": ("ffc060ff", "http://maps.google.com/mapfiles/kml/paddle/purple-circle.png", 1.0),
    "water": ("ffffaa00", "http://maps.google.com/mapfiles/kml/paddle/blu-circle.png", 1.0),
    "unresolved": ("ffcccccc", "http://maps.google.com/mapfiles/kml/paddle/wht-circle.png", 0.9),
    "intersection": ("ff888888", "http://maps.google.com/mapfiles/kml/shapes/shaded_dot.png", 0.45),
    "gcp": ("ff00ffff", "http://maps.google.com/mapfiles/kml/paddle/ltblu-stars.png", 1.15),
}


def kml_styles() -> str:
    chunks = []
    for key, (color, href, scale) in STYLES.items():
        chunks.append(
            f"""  <Style id="s-{key}">
    <IconStyle>
      <color>{color}</color>
      <scale>{scale}</scale>
      <Icon><href>{href}</href></Icon>
    </IconStyle>
    <LabelStyle><scale>{"0.85" if key != "intersection" else "0"}</scale></LabelStyle>
    <BalloonStyle><text><![CDATA[<b>$[name]</b><br/>$[description]]]></text></BalloonStyle>
  </Style>"""
        )
    chunks.append(
        """  <Style id="s-edge">
    <LineStyle><color>ff2060ff</color><width>3.2</width></LineStyle>
    <LabelStyle><scale>0</scale></LabelStyle>
  </Style>"""
    )
    return "\n".join(chunks)


def balloon(row: dict) -> str:
    parts = []
    if row.get("landmark_id"):
        parts.append(f"legend {escape(row['landmark_id'])}")
    if row.get("raw_code") and row.get("raw_code") != row.get("landmark_id"):
        parts.append(f"drawn as {escape(row['raw_code'])}")
    if row.get("confidence"):
        parts.append(f"match {escape(row['confidence'])} ({escape(row.get('match_method') or '')})")
    if row.get("georef_role"):
        extra = row.get("georef_residual_m")
        role = row["georef_role"]
        if extra:
            role += f", residual {extra} m"
        parts.append(escape(role))
    parts.append(f"{escape(row['lat'])}, {escape(row['lon'])}")
    if row.get("notes"):
        parts.append(escape(row["notes"]))
    if row.get("alternatives"):
        parts.append("alternatives: " + escape(row["alternatives"]))
    return "<br/>".join(parts)


def point_placemark(row: dict, style: str) -> str:
    name = row.get("landmark_name") or row.get("Label") or row["Id"]
    if row.get("landmark_id") and row.get("landmark_name"):
        name = f"{row['landmark_id']} {row['landmark_name']}"
    return f"""    <Placemark>
      <name>{escape(name)}</name>
      <styleUrl>#s-{style}</styleUrl>
      <description>{balloon(row)}</description>
      <ExtendedData>
        <Data name="Id"><value>{escape(row['Id'])}</value></Data>
        <Data name="landmark_id"><value>{escape(row.get('landmark_id') or '')}</value></Data>
      </ExtendedData>
      <Point><coordinates>{row['lon']},{row['lat']},0</coordinates></Point>
    </Placemark>"""


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    from math import radians, sin, cos, asin, sqrt

    r = 6371000.0
    p1, p2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlmb = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(p1) * cos(p2) * sin(dlmb / 2) ** 2
    return 2 * r * asin(sqrt(a))


def nearest_street(mid_x: float, mid_y: float, streets: list[dict]) -> dict | None:
    if not streets:
        return None
    best, best_d = None, float("inf")
    for s in streets:
        d = ((float(s["x"]) - mid_x) ** 2 + (float(s["y"]) - mid_y) ** 2) ** 0.5
        if d < best_d:
            best, best_d = s, d
    # digitizer units are roughly metres-on-the-drawing, not ground metres
    if best is None or best_d > 180:
        return None
    return best


def enrich_edges(edges: list[dict], by_id: dict, streets: list[dict]) -> list[dict]:
    out = []
    for e in edges:
        a, b = by_id.get(e["Source"]), by_id.get(e["Target"])
        if not a or not b or not a.get("lon") or not b.get("lon"):
            continue
        lon1, lat1 = float(a["lon"]), float(a["lat"])
        lon2, lat2 = float(b["lon"]), float(b["lat"])
        mid_x = (float(a["x"]) + float(b["x"])) / 2
        mid_y = (float(a["y"]) + float(b["y"])) / 2
        street = nearest_street(mid_x, mid_y, streets)
        out.append(
            {
                "Id": e["Id"],
                "Source": e["Source"],
                "Target": e["Target"],
                "Type": e.get("Type") or "Undirected",
                "Weight": e.get("Weight") or "1",
                "source_label": a.get("Label") or "",
                "target_label": b.get("Label") or "",
                "source_lon": a["lon"],
                "source_lat": a["lat"],
                "target_lon": b["lon"],
                "target_lat": b["lat"],
                "length_m": f"{haversine_m(lon1, lat1, lon2, lat2):.1f}",
                "nearest_street_id": (street or {}).get("landmark_id") or "",
                "nearest_street_name": (street or {}).get("landmark_name") or "",
            }
        )
    return out


def edge_placemark(e: dict) -> str:
    name = f"edge {e['Id']}"
    if e["nearest_street_name"]:
        name = f"{e['nearest_street_id']} {e['nearest_street_name']}"
    desc = "<br/>".join(
        [
            f"edge {escape(e['Id'])}: node {escape(e['Source'])} → {escape(e['Target'])}",
            f"{escape(e['source_label'])} → {escape(e['target_label'])}",
            f"{escape(e['length_m'])} m",
            f"{escape(e['source_lat'])}, {escape(e['source_lon'])} → {escape(e['target_lat'])}, {escape(e['target_lon'])}",
        ]
    )
    if e["nearest_street_name"]:
        desc += f"<br/>nearest street marker: {escape(e['nearest_street_id'])} {escape(e['nearest_street_name'])}"
    return f"""    <Placemark>
      <name>{escape(name)}</name>
      <styleUrl>#s-edge</styleUrl>
      <description>{desc}</description>
      <ExtendedData>
        <Data name="Id"><value>{escape(e['Id'])}</value></Data>
        <Data name="Source"><value>{escape(e['Source'])}</value></Data>
        <Data name="Target"><value>{escape(e['Target'])}</value></Data>
      </ExtendedData>
      <LineString>
        <tessellate>1</tessellate>
        <coordinates>{e['source_lon']},{e['source_lat']},0 {e['target_lon']},{e['target_lat']},0</coordinates>
      </LineString>
    </Placemark>"""


def folder(name: str, open_flag: int, body: str) -> str:
    return f"""  <Folder>
    <name>{escape(name)}</name>
    <open>{open_flag}</open>
{body}
  </Folder>"""


def main() -> None:
    with NODES.open(encoding="utf-8", newline="") as f:
        nodes = list(csv.DictReader(f))
    with EDGES.open(encoding="utf-8", newline="") as f:
        edges = list(csv.DictReader(f))

    by_id = {r["Id"]: r for r in nodes}
    markers = [r for r in nodes if r["node_kind"] == "marker"]
    intersections = [r for r in nodes if r["node_kind"] == "intersection"]
    streets = [r for r in markers if r.get("landmark_kind") == "street" and r.get("landmark_id")]
    fuzzy_edges = enrich_edges(edges, by_id, streets)

    edge_fields = [
        "Id", "Source", "Target", "Type", "Weight",
        "source_label", "target_label",
        "source_lon", "source_lat", "target_lon", "target_lat",
        "length_m", "nearest_street_id", "nearest_street_name",
    ]
    with OUT_EDGES.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=edge_fields)
        w.writeheader()
        w.writerows(fuzzy_edges)

    kind_folders = []
    kind_order = ["building", "street", "direction", "district", "water", "unresolved"]
    by_kind: dict[str, list] = {k: [] for k in kind_order}
    for r in markers:
        k = r.get("landmark_kind") or "unresolved"
        if k not in by_kind:
            k = "unresolved"
        by_kind[k].append(r)
    for k in kind_order:
        rows = by_kind[k]
        if not rows:
            continue
        body = "\n".join(point_placemark(r, k) for r in rows)
        kind_folders.append(folder(f"{k} ({len(rows)})", 1 if k == "building" else 0, body))

    gcps = [r for r in markers if r.get("georef_role") == "gcp"]
    gcp_folder = folder(
        f"control points used for georeference ({len(gcps)})",
        0,
        "\n".join(point_placemark(r, "gcp") for r in gcps),
    )

    inter_body = "\n".join(point_placemark(r, "intersection") for r in intersections)
    inter_folder = folder(f"street-graph vertices ({len(intersections)})", 0, inter_body)

    edge_folder = folder(
        f"street graph from edges.csv ({len(fuzzy_edges)} edges)",
        1,
        "\n".join(edge_placemark(e) for e in fuzzy_edges),
    )

    kml = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
  <name>Kowel 1939 map graph</name>
  <open>1</open>
  <description>Georeferenced digitization of the c.1939 Kowel landmark map. Orange lines are edges.csv (street graph). Pins are landmarks. Stars are control points used to warp drawing coordinates onto WGS84.</description>
  <LookAt>
    <longitude>24.7087</longitude>
    <latitude>51.2153</latitude>
    <altitude>0</altitude>
    <heading>0</heading>
    <tilt>0</tilt>
    <range>6500</range>
    <altitudeMode>relativeToGround</altitudeMode>
  </LookAt>
{kml_styles()}
{edge_folder}
{folder("landmarks", 1, chr(10).join(kind_folders))}
{gcp_folder}
{inter_folder}
</Document>
</kml>
"""

    with zipfile.ZipFile(OUT_KMZ, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("doc.kml", kml)
    print(f"wrote {OUT_EDGES} ({len(fuzzy_edges)} edges)")
    print(f"wrote {OUT_KMZ} ({OUT_KMZ.stat().st_size} bytes)")
    print(f"markers={len(markers)} intersections={len(intersections)} edges={len(fuzzy_edges)} gcps={len(gcps)}")


if __name__ == "__main__":
    main()
