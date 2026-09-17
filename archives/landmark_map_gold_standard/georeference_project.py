#!/usr/bin/env python3
"""Add WGS84 lon/lat to a map-graph-digitizer project JSON.

Control points come from correct-locations-kowel.geojson.kmz (WGS84),
matched to unique landmark ids on marker nodes. The 1939 drawing is not
to scale, so an affine fit is only used to reject mismatched pairs; the
coordinates written onto nodes are a thin-plate spline of the inliers.

Image x/y are left unchanged. The source project file is not overwritten.
"""

from __future__ import annotations

import json
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

import numpy as np
from pyproj import Transformer
from scipy.interpolate import RBFInterpolator

HERE = Path(__file__).resolve().parent
SRC_PATH = HERE / "annotation_backup" / "map-graph-project.2026-09-16.json"
OUT_PATH = HERE / "map-graph-project.georef.json"
KMZ_PATH = Path(r"D:\Kowel_Redux\cities\kowel\geospatial\correct-locations-kowel.geojson.kmz")

# KMZ L2 is the pedestrian tunnel; our L2 is NKVD.
# KMZ L1 is an execution site, not Holtschein's house.
# G4 / A4 / B2 disagree on neighborhood between the drawing and the KMZ.
DENY_CODES = {"L2", "L1", "G4", "A4", "B2"}

TO_UTM = Transformer.from_crs("EPSG:4326", "EPSG:32635", always_xy=True)
TO_WGS84 = Transformer.from_crs("EPSG:32635", "EPSG:4326", always_xy=True)

GEO_STREETS = {
    "ulica Warszawska": "27",
    "Ulica Szpitalna": "55",
    "Okolica Piaski": "60",
}

E_TO_I = {"E1": "I1", "E2": "I2", "E3": "I3"}

KML_NS = {"kml": "http://www.opengis.net/kml/2.2"}

SPOT_CHECKS = {
    "A1": "Great Synagogue",
    "F1": "Orthodox cathedral",
    "M6": "Friedrichson pharmacy",
    "D7": "Polish hospital",
    "J6": "water tower",
    "F3": "Catholic church",
    "A11": "Entina synagogue",
    "J1": "rynek",
}


def parse_geo_code(name: str) -> str | None:
    name = name.strip()
    m = re.match(r"^([A-Z])\.?\s*(\d+)\b", name)
    if m:
        return m.group(1) + m.group(2)
    return GEO_STREETS.get(name)


def load_kmz(path: Path) -> dict[str, list[tuple]]:
    with zipfile.ZipFile(path) as z:
        kml = z.read("doc.kml")
    root = ET.fromstring(kml)
    by: dict[str, list[tuple]] = defaultdict(list)
    for pm in root.findall(".//kml:Placemark", KML_NS):
        name_el = pm.find("kml:name", KML_NS)
        coord_el = pm.find(".//kml:coordinates", KML_NS)
        if name_el is None or coord_el is None or not (coord_el.text or "").strip():
            continue
        name = (name_el.text or "").strip()
        lon_s, lat_s, *_ = coord_el.text.strip().split(",")
        lon, lat = float(lon_s), float(lat_s)
        east, north = TO_UTM.transform(lon, lat)
        code = parse_geo_code(name)
        by[code or "?"].append((name, float(east), float(north), lon, lat))
    return by


def extra(node: dict) -> dict:
    ex = node.get("extra")
    return ex if isinstance(ex, dict) else {}


def collect_gcps(nodes: list[dict], geo_by: dict) -> list[dict]:
    by_lid: dict[str, list[dict]] = defaultdict(list)
    for node in nodes:
        if extra(node).get("node_kind") != "marker":
            continue
        lid = extra(node).get("landmark_id")
        if lid:
            by_lid[str(lid)].append(node)

    gcps = []
    for code, feats in geo_by.items():
        if not code or code == "?" or code in DENY_CODES:
            continue
        lid = E_TO_I.get(code, code)
        matched = by_lid.get(lid, [])
        if len(feats) != 1 or len(matched) != 1:
            continue
        node = matched[0]
        name, east, north, lon, lat = feats[0]
        gcps.append(
            {
                "node_id": node["id"],
                "code": code,
                "lid": lid,
                "label": node.get("label") or "",
                "x": float(node["x"]),
                "y": float(node["y"]),
                "east": east,
                "north": north,
                "lon": lon,
                "lat": lat,
                "geo_name": name,
            }
        )

    # Stock exchange: KMZ I4 ↔ marker_I4 (no landmark_id in the project).
    i4_nodes = [
        n for n in nodes
        if str(n.get("label") or "") in {"marker_I4", "I4"}
        or extra(n).get("landmark_id") == "I4"
    ]
    if len(i4_nodes) == 1 and len(geo_by.get("I4", [])) == 1:
        if not any(g["node_id"] == i4_nodes[0]["id"] for g in gcps):
            node = i4_nodes[0]
            name, east, north, lon, lat = geo_by["I4"][0]
            gcps.append(
                {
                    "node_id": node["id"],
                    "code": "I4",
                    "lid": "I4",
                    "label": node.get("label") or "",
                    "x": float(node["x"]),
                    "y": float(node["y"]),
                    "east": east,
                    "north": north,
                    "lon": lon,
                    "lat": lat,
                    "geo_name": name,
                }
            )
    return gcps


def affine_predict(gcps: list[dict], xs: np.ndarray, ys: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    A = np.column_stack([np.array([g["x"] for g in gcps]), np.array([g["y"] for g in gcps]), np.ones(len(gcps))])
    east = np.array([g["east"] for g in gcps])
    north = np.array([g["north"] for g in gcps])
    ae, *_ = np.linalg.lstsq(A, east, rcond=None)
    an, *_ = np.linalg.lstsq(A, north, rcond=None)
    pred_e = ae[0] * xs + ae[1] * ys + ae[2]
    pred_n = an[0] * xs + an[1] * ys + an[2]
    gcp_res = np.hypot(
        (ae[0] * A[:, 0] + ae[1] * A[:, 1] + ae[2]) - east,
        (an[0] * A[:, 0] + an[1] * A[:, 1] + an[2]) - north,
    )
    return pred_e, pred_n, gcp_res


def ransac_inliers(gcps: list[dict], threshold_m: float = 350.0, iters: int = 400, seed: int = 1) -> list[dict]:
    rng = np.random.default_rng(seed)
    n = len(gcps)
    if n < 4:
        return gcps
    best: list[dict] = []
    idx = np.arange(n)
    for _ in range(iters):
        sample_i = rng.choice(n, size=3, replace=False)
        sample = [gcps[i] for i in sample_i]
        xs = np.array([g["x"] for g in gcps])
        ys = np.array([g["y"] for g in gcps])
        pred_e, pred_n, _ = affine_predict(sample, xs, ys)
        east = np.array([g["east"] for g in gcps])
        north = np.array([g["north"] for g in gcps])
        res = np.hypot(pred_e - east, pred_n - north)
        inlier_i = idx[res <= threshold_m]
        if len(inlier_i) > len(best):
            best = [gcps[i] for i in inlier_i]
    if len(best) >= 4:
        xs = np.array([g["x"] for g in best])
        ys = np.array([g["y"] for g in best])
        _, _, res = affine_predict(best, xs, ys)
        best = [g for g, r in zip(best, res) if r <= threshold_m]
    return best if len(best) >= 4 else gcps


def fit_tps(gcps: list[dict], smoothing: float) -> RBFInterpolator:
    src = np.column_stack([[g["x"] for g in gcps], [g["y"] for g in gcps]])
    dst = np.column_stack([[g["east"] for g in gcps], [g["north"] for g in gcps]])
    return RBFInterpolator(src, dst, kernel="thin_plate_spline", smoothing=smoothing)


def main() -> None:
    if not SRC_PATH.exists():
        raise SystemExit(f"missing project file: {SRC_PATH}")
    if not KMZ_PATH.exists():
        raise SystemExit(f"missing control-point file: {KMZ_PATH}")

    project = json.loads(SRC_PATH.read_text(encoding="utf-8"))
    if project.get("type") != "map-graph-digitizer-project":
        raise SystemExit(f"not a map-graph-digitizer project: {SRC_PATH}")
    nodes = project.get("nodes") or []
    n_edges = len(project.get("edges") or [])

    geo_by = load_kmz(KMZ_PATH)
    n_placemarks = sum(len(v) for v in geo_by.values())
    print(f"project {SRC_PATH.name}: {len(nodes)} nodes, {n_edges} edges")
    print(f"KMZ placemarks: {n_placemarks}")

    gcps_all = collect_gcps(nodes, geo_by)
    print(f"candidate GCPs: {len(gcps_all)}")

    inliers = ransac_inliers(gcps_all, threshold_m=350)
    inlier_ids = {g["node_id"] for g in inliers}
    print(f"RANSAC inliers @350 m: {len(inliers)}")
    for g in sorted(gcps_all, key=lambda r: (str(r["lid"]), r["node_id"])):
        flag = "IN" if g["node_id"] in inlier_ids else "OUT"
        print(f"  {flag:3s} node {g['node_id']:<4} {g['lid']:4s} {g['label']:18s} {g['geo_name'][:42]}")

    if len(inliers) < 4:
        raise SystemExit("not enough GCP inliers to fit a spline")

    xs = np.array([g["x"] for g in inliers])
    ys = np.array([g["y"] for g in inliers])
    _, _, affine_res = affine_predict(inliers, xs, ys)
    print(
        f"\ninlier affine RMSE {np.sqrt(np.mean(affine_res**2)):.0f} m  "
        f"median {np.median(affine_res):.0f} m  max {affine_res.max():.0f} m"
    )

    smoothing = 250.0
    tps = fit_tps(inliers, smoothing=smoothing)
    pred = tps(np.column_stack([xs, ys]))
    tps_res = np.hypot(
        pred[:, 0] - np.array([g["east"] for g in inliers]),
        pred[:, 1] - np.array([g["north"] for g in inliers]),
    )
    print(
        f"TPS smoothing={smoothing:g}  RMSE {np.sqrt(np.mean(tps_res**2)):.0f} m  "
        f"median {np.median(tps_res):.0f} m  max {tps_res.max():.0f} m"
    )

    residual_by_id = {g["node_id"]: float(r) for g, r in zip(inliers, tps_res)}
    candidate_ids = {g["node_id"] for g in gcps_all}

    all_xy = np.column_stack([[float(n["x"]) for n in nodes], [float(n["y"]) for n in nodes]])
    utm = tps(all_xy)
    lons, lats = TO_WGS84.transform(utm[:, 0], utm[:, 1])
    lons = np.asarray(lons, dtype=float)
    lats = np.asarray(lats, dtype=float)

    print(
        "\nWGS84 bbox: lon {:.5f}..{:.5f}  lat {:.5f}..{:.5f}".format(
            float(np.min(lons)), float(np.max(lons)), float(np.min(lats)), float(np.max(lats))
        )
    )
    if not (24.55 < float(np.median(lons)) < 24.85 and 51.15 < float(np.median(lats)) < 51.30):
        raise SystemExit("median lon/lat is not in Kovel; aborting")

    for node, lon, lat in zip(nodes, lons, lats):
        node["lon"] = round(float(lon), 7)
        node["lat"] = round(float(lat), 7)
        ex = extra(node)
        if node.get("extra") is not ex:
            node["extra"] = ex
        nid = node["id"]
        if nid in residual_by_id:
            ex["georef_role"] = "gcp"
            ex["georef_residual_m"] = round(residual_by_id[nid], 1)
        elif nid in candidate_ids:
            ex["georef_role"] = "gcp_outlier"
            ex.pop("georef_residual_m", None)
        else:
            ex["georef_role"] = "interpolated"
            ex.pop("georef_residual_m", None)

    project["nodes"] = nodes
    OUT_PATH.write_text(
        json.dumps(project, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"wrote {OUT_PATH} ({len(nodes)} nodes, {len(inliers)} GCPs)")

    print("\nspot checks (TPS):")
    for node in nodes:
        lid = extra(node).get("landmark_id")
        if lid not in SPOT_CHECKS:
            continue
        print(
            f"  {lid:4s} {SPOT_CHECKS[lid]:24s}  "
            f"{node['lat']}, {node['lon']}  role={extra(node).get('georef_role')}  "
            f"resid={extra(node).get('georef_residual_m', '')}"
        )


if __name__ == "__main__":
    main()
