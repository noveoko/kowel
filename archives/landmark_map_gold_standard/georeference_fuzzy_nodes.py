#!/usr/bin/env python3
"""Add WGS84 lon/lat (and UTM 35N) columns to fuzzy_nodes.csv.

Control points come from maps/correct-locations-kowel.geojson (EPSG:32635),
matched to unique high-confidence landmark ids. The 1939 drawing is not to
scale, so an affine fit is only used to reject mismatched pairs; the
coordinates written to the CSV are a thin-plate spline of the inliers.
"""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

import numpy as np
from pyproj import Transformer
from scipy.interpolate import RBFInterpolator

HERE = Path(__file__).resolve().parent
FUZZY_PATH = HERE / "fuzzy_nodes.csv"
GEOJSON_PATH = HERE.parent.parent / "maps" / "correct-locations-kowel.geojson"

# GeoJSON L2 is the pedestrian tunnel; our L2 is NKVD.
# GeoJSON L1 is an execution site, not Holtschein's house.
# G4 / A4 / B2 disagree on neighborhood between the drawing and the GeoJSON.
DENY_CODES = {"L2", "L1", "G4", "A4", "B2"}

TO_WGS84 = Transformer.from_crs("EPSG:32635", "EPSG:4326", always_xy=True)

GEO_STREETS = {
    "ulica Warszawska": "27",
    "Ulica Szpitalna": "55",
    "Okolica Piaski": "60",
}

E_TO_I = {"E1": "I1", "E2": "I2", "E3": "I3"}

OUT_FIELDS = [
    "Id", "Label", "x", "y", "pixel_x", "pixel_y",
    "lon", "lat", "utm_easting", "utm_northing",
    "node_kind", "raw_code", "annotator_uncertain",
    "landmark_id", "landmark_name", "landmark_kind",
    "match_method", "confidence", "alternatives", "notes",
    "nearest_marker_id",
    "georef_role", "georef_residual_m",
]


def parse_geo_code(name: str) -> str | None:
    name = name.strip()
    m = re.match(r"^([A-Z])\.?\s*(\d+)\b", name)
    if m:
        return m.group(1) + m.group(2)
    return GEO_STREETS.get(name)


def load_geo(path: Path) -> dict[str, list[tuple]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    by: dict[str, list[tuple]] = defaultdict(list)
    for feat in data["features"]:
        name = feat["properties"]["name"]
        code = parse_geo_code(name)
        east, north = feat["geometry"]["coordinates"]
        lon, lat = TO_WGS84.transform(east, north)
        by[code or "?"].append((name, float(east), float(north), float(lon), float(lat)))
    return by


def collect_gcps(fuzzy: list[dict], geo_by: dict) -> list[dict]:
    by_lid: dict[str, list[dict]] = defaultdict(list)
    for row in fuzzy:
        if row.get("node_kind") == "marker" and row.get("landmark_id"):
            by_lid[row["landmark_id"]].append(row)

    gcps = []
    for code, feats in geo_by.items():
        if not code or code == "?" or code in DENY_CODES:
            continue
        lid = E_TO_I.get(code, code)
        nodes = by_lid.get(lid, [])
        if len(feats) != 1 or len(nodes) != 1:
            continue
        node = nodes[0]
        conf = float(node.get("confidence") or 0)
        method = node.get("match_method") or ""
        if conf < 0.80:
            continue
        if method not in {"exact_unique", "street_repeat", "letter_shift", "typo_fix"}:
            continue
        name, east, north, lon, lat = feats[0]
        gcps.append(
            {
                "node_id": node["Id"],
                "code": code,
                "lid": lid,
                "label": node["Label"],
                "x": float(node["x"]),
                "y": float(node["y"]),
                "east": east,
                "north": north,
                "lon": lon,
                "lat": lat,
                "geo_name": name,
                "conf": conf,
            }
        )

    # Stock exchange: geo I4 ↔ marker_I4 (unmatched in the transcribed legend).
    i4_nodes = [r for r in fuzzy if r.get("raw_code") == "I4"]
    if len(i4_nodes) == 1 and len(geo_by.get("I4", [])) == 1:
        node = i4_nodes[0]
        name, east, north, lon, lat = geo_by["I4"][0]
        gcps.append(
            {
                "node_id": node["Id"],
                "code": "I4",
                "lid": "I4",
                "label": node["Label"],
                "x": float(node["x"]),
                "y": float(node["y"]),
                "east": east,
                "north": north,
                "lon": lon,
                "lat": lat,
                "geo_name": name,
                "conf": 0.70,
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
    best = []
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
    # Refit affine on inliers and drop remaining outliers.
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
    if not GEOJSON_PATH.exists():
        raise SystemExit(f"missing control-point file: {GEOJSON_PATH}")

    with FUZZY_PATH.open(encoding="utf-8", newline="") as f:
        fuzzy = list(csv.DictReader(f))

    geo_by = load_geo(GEOJSON_PATH)
    gcps_all = collect_gcps(fuzzy, geo_by)
    print(f"candidate GCPs: {len(gcps_all)}")

    inliers = ransac_inliers(gcps_all, threshold_m=350)
    inlier_ids = {g["node_id"] for g in inliers}
    print(f"RANSAC inliers @350 m: {len(inliers)}")
    for g in gcps_all:
        flag = "IN" if g["node_id"] in inlier_ids else "OUT"
        print(f"  {flag:3s} node {g['node_id']:4s} {g['lid']:4s} {g['label']:18s} {g['geo_name'][:42]}")

    xs = np.array([g["x"] for g in inliers])
    ys = np.array([g["y"] for g in inliers])
    _, _, affine_res = affine_predict(inliers, xs, ys)
    print(f"\ninlier affine RMSE {np.sqrt(np.mean(affine_res**2)):.0f} m  "
          f"median {np.median(affine_res):.0f} m  max {affine_res.max():.0f} m")

    # Smoothing in metres²-ish; keep GCP error small but don't interpolate noise.
    smoothing = 250.0
    tps = fit_tps(inliers, smoothing=smoothing)
    src = np.column_stack([xs, ys])
    pred = tps(src)
    tps_res = np.hypot(pred[:, 0] - np.array([g["east"] for g in inliers]),
                       pred[:, 1] - np.array([g["north"] for g in inliers]))
    print(f"TPS smoothing={smoothing:g}  RMSE {np.sqrt(np.mean(tps_res**2)):.0f} m  "
          f"median {np.median(tps_res):.0f} m  max {tps_res.max():.0f} m")

    residual_by_id = {g["node_id"]: float(r) for g, r in zip(inliers, tps_res)}

    all_xy = np.column_stack(
        [[float(r["x"]) for r in fuzzy], [float(r["y"]) for r in fuzzy]]
    )
    utm = tps(all_xy)
    lons, lats = TO_WGS84.transform(utm[:, 0], utm[:, 1])

    print("\nWGS84 bbox: lon {:.5f}..{:.5f}  lat {:.5f}..{:.5f}".format(
        float(np.min(lons)), float(np.max(lons)), float(np.min(lats)), float(np.max(lats))
    ))
    # Kovel city is roughly 24.68–24.76 E, 51.20–51.24 N. Warn if we jumped.
    if not (24.55 < float(np.median(lons)) < 24.85 and 51.15 < float(np.median(lats)) < 51.30):
        raise SystemExit("median lon/lat is not in Kovel; aborting")

    for row, east, north, lon, lat in zip(fuzzy, utm[:, 0], utm[:, 1], lons, lats):
        row["utm_easting"] = f"{east:.2f}"
        row["utm_northing"] = f"{north:.2f}"
        row["lon"] = f"{lon:.7f}"
        row["lat"] = f"{lat:.7f}"
        if row["Id"] in residual_by_id:
            row["georef_role"] = "gcp"
            row["georef_residual_m"] = f"{residual_by_id[row['Id']]:.1f}"
        elif row["Id"] in {g["node_id"] for g in gcps_all}:
            row["georef_role"] = "gcp_outlier"
            row["georef_residual_m"] = ""
        else:
            row["georef_role"] = "interpolated"
            row["georef_residual_m"] = ""

    with FUZZY_PATH.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OUT_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(fuzzy)
    print(f"wrote {FUZZY_PATH} ({len(fuzzy)} rows, {len(inliers)} GCPs)")

    # Spot-check surviving buildings.
    print("\nspot checks (TPS):")
    want = {"A1": "Great Synagogue", "F1": "Orthodox cathedral", "M6": "Friedrichson pharmacy",
            "D7": "Polish hospital", "J6": "water tower", "F3": "Catholic church",
            "A11": "Entina synagogue", "J1": "rynek"}
    for row in fuzzy:
        if row.get("landmark_id") in want:
            print(f"  {row['landmark_id']:4s} {want[row['landmark_id']]:24s}  "
                  f"{row['lat']}, {row['lon']}  role={row['georef_role']}  "
                  f"resid={row['georef_residual_m']}")


if __name__ == "__main__":
    main()
