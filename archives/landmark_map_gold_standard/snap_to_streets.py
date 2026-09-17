#!/usr/bin/env python3
"""Snap the 1939 schematic street graph onto OSM centerlines.

Landmarks stay put (anchors). Junctions are matched 1-1 to OSM intersections
(graph ICP + TPS). Degree-2 vertices slide along the OSM shortest path between
matched ends. Unmatched strokes are left as TPS chords and flagged.
"""

from __future__ import annotations

import csv
import json
import math
import urllib.parse
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path

import networkx as nx
import numpy as np
from pyproj import Transformer
from scipy.interpolate import RBFInterpolator
from scipy.optimize import linear_sum_assignment
from shapely.geometry import LineString, Point

HERE = Path(__file__).resolve().parent
NODES_IN = HERE / "fuzzy_nodes.csv"
EDGES_IN = HERE / "edges.csv"
CACHE = HERE / "osm_cache" / "kowel_highways.json"
OUT_NODES = HERE / "fuzzy_nodes_snapped.csv"
OUT_EDGES = HERE / "fuzzy_edges_snapped.csv"
OUT_KMZ = HERE / "kowel-snapped.kmz"

TO_UTM = Transformer.from_crs("EPSG:4326", "EPSG:32635", always_xy=True)
TO_LL = Transformer.from_crs("EPSG:32635", "EPSG:4326", always_xy=True)

# Matching / routing knobs
ICP_ITERS = 5
START_RADIUS = 130.0
END_RADIUS = 45.0
REJECT_COST = 160.0  # metres-equivalent
ALPHA_DEG = 18.0     # metres per degree mismatch
BETA_BEARING = 25.0  # metres at worst bearing mismatch
TPS_SMOOTH = 80.0
MAX_DETOUR = 2.2
STROKE_BUFFER = 110.0  # metres: OSM subgraph around a schematic stroke
MIN_HIGHWAYS = {
    "motorway", "trunk", "primary", "secondary", "tertiary", "unclassified",
    "residential", "living_street", "pedestrian", "service", "road",
}
OVERPASS_ENDPOINTS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    r = 6371000.0
    p = math.pi / 180
    dphi = (lat2 - lat1) * p
    dl = (lon2 - lon1) * p
    a = math.sin(dphi / 2) ** 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(min(1.0, a)))


def load_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def fetch_osm(south, west, north, east) -> dict:
    CACHE.parent.mkdir(exist_ok=True)
    if CACHE.exists():
        return json.loads(CACHE.read_text(encoding="utf-8"))
    hw = "|".join(sorted(MIN_HIGHWAYS))
    query = f"""
[out:json][timeout:60];
way["highway"~"^({hw})$"]({south:.5f},{west:.5f},{north:.5f},{east:.5f});
out geom;
"""
    data = urllib.parse.urlencode({"data": query}).encode()
    last_err = None
    for url in OVERPASS_ENDPOINTS:
        print(f"fetching OSM highways from {url} …")
        req = urllib.request.Request(url, data=data, headers={"User-Agent": "kowel-snap/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            CACHE.write_text(json.dumps(payload), encoding="utf-8")
            print(f"cached {CACHE} ({len(payload.get('elements', []))} ways)")
            return payload
        except Exception as exc:
            last_err = exc
            print(f"  failed: {exc}")
    raise RuntimeError(f"Overpass failed: {last_err}")


def build_osm_graph(payload: dict) -> nx.Graph:
    G = nx.Graph()
    for el in payload.get("elements", []):
        if el.get("type") != "way":
            continue
        hw = (el.get("tags") or {}).get("highway", "")
        if hw not in MIN_HIGHWAYS:
            continue
        geom = el.get("geometry") or []
        nodes = el.get("nodes") or []
        if len(geom) < 2:
            continue
        ids = nodes if len(nodes) == len(geom) else [f"{el['id']}:{i}" for i in range(len(geom))]
        for nid, pt in zip(ids, geom):
            e, n = TO_UTM.transform(pt["lon"], pt["lat"])
            if nid not in G:
                G.add_node(nid, east=e, north=n, lon=pt["lon"], lat=pt["lat"])
        for a, b, p, q in zip(ids, ids[1:], geom, geom[1:]):
            length = haversine_m(p["lat"], p["lon"], q["lat"], q["lon"])
            if length <= 0:
                continue
            if G.has_edge(a, b):
                G[a][b]["length"] = min(G[a][b]["length"], length)
            else:
                G.add_edge(a, b, length=length)
    return G


def schematic_graph(nodes: list[dict], edges: list[dict]):
    by_id = {int(r["Id"]): r for r in nodes}
    adj = defaultdict(list)
    for e in edges:
        s, t = int(e["Source"]), int(e["Target"])
        adj[s].append(t)
        adj[t].append(s)
    deg = {i: len(set(adj[i])) for i in by_id}
    return by_id, adj, deg


def bearings(uid: int, adj, pos) -> list[float]:
    x, y = pos[uid]
    out = []
    for v in set(adj[uid]):
        if v not in pos:
            continue
        dx, dy = pos[v][0] - x, pos[v][1] - y
        if dx == 0 and dy == 0:
            continue
        out.append(math.atan2(dy, dx))
    return out


def bearing_cost(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 1.0
    # circular difference, Hungarian on the smaller set
    n, m = len(a), len(b)
    C = np.ones((n, m))
    for i, ai in enumerate(a):
        for j, bj in enumerate(b):
            d = abs(ai - bj) % (2 * math.pi)
            d = min(d, 2 * math.pi - d)
            C[i, j] = d / math.pi  # 0..1
    if n <= m:
        ri, ci = linear_sum_assignment(C)
        return float(C[ri, ci].mean()) if len(ri) else 1.0
    ri, ci = linear_sum_assignment(C.T)
    return float(C.T[ri, ci].mean()) if len(ri) else 1.0


def match_junctions(junc_ids, pos, deg, adj, osm_junc, radius):
    """Return dict schematic_id -> osm_id (1-1, cost-rejected)."""
    osm_ids = list(osm_junc)
    if not junc_ids or not osm_ids:
        return {}
    n, m = len(junc_ids), len(osm_ids)
    BIG = 1e9
    C = np.full((n, m), BIG)
    for i, uid in enumerate(junc_ids):
        ux, uy = pos[uid]
        ub = bearings(uid, adj, pos)
        for j, oid in enumerate(osm_ids):
            ox, oy = osm_junc[oid]["east"], osm_junc[oid]["north"]
            d = math.hypot(ux - ox, uy - oy)
            if d > radius:
                continue
            dd = abs(deg[uid] - osm_junc[oid]["deg"])
            bc = bearing_cost(ub, osm_junc[oid]["bearings"])
            C[i, j] = d + ALPHA_DEG * dd + BETA_BEARING * bc
    ri, ci = linear_sum_assignment(C)
    out = {}
    used = set()
    for i, j in zip(ri, ci):
        if C[i, j] >= REJECT_COST or C[i, j] >= BIG / 2:
            continue
        out[junc_ids[i]] = osm_ids[j]
        used.add(osm_ids[j])
    return out


def fit_tps(ctrl_src: np.ndarray, ctrl_dst: np.ndarray, query: np.ndarray, smoothing: float):
    if len(ctrl_src) < 3:
        return query
    rbf = RBFInterpolator(ctrl_src, ctrl_dst, kernel="thin_plate_spline", smoothing=smoothing)
    return rbf(query)


def strokes_from(adj, deg, node_ids):
    """Maximal paths whose interior vertices all have degree 2."""
    street_ids = [i for i in node_ids if deg.get(i, 0) >= 1]
    terminals = {i for i in street_ids if deg[i] != 2}
    visited_edges = set()
    strokes = []

    def key(a, b):
        return (a, b) if a < b else (b, a)

    for start in sorted(terminals):
        for nb in set(adj[start]):
            ek = key(start, nb)
            if ek in visited_edges:
                continue
            path = [start, nb]
            visited_edges.add(ek)
            prev, cur = start, nb
            while deg.get(cur, 0) == 2:
                nxts = [x for x in set(adj[cur]) if x != prev]
                if not nxts:
                    break
                nxt = nxts[0]
                ek = key(cur, nxt)
                if ek in visited_edges and nxt != start:
                    break
                visited_edges.add(ek)
                path.append(nxt)
                prev, cur = cur, nxt
                if cur in terminals:
                    break
            strokes.append(path)
    return strokes


def polyline_length(pts: list[tuple[float, float]]) -> float:
    return sum(math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]) for i in range(1, len(pts)))


def interpolate_along(pts: list[tuple[float, float]], fractions: list[float]) -> list[tuple[float, float]]:
    if len(pts) == 1:
        return [pts[0]] * len(fractions)
    seglen = [math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]) for i in range(1, len(pts))]
    total = sum(seglen) or 1.0
    acc = [0.0]
    for L in seglen:
        acc.append(acc[-1] + L)
    out = []
    for f in fractions:
        d = max(0.0, min(1.0, f)) * total
        k = 1
        while k < len(acc) - 1 and acc[k] < d:
            k += 1
        t = 0 if seglen[k - 1] == 0 else (d - acc[k - 1]) / seglen[k - 1]
        x = pts[k - 1][0] + t * (pts[k][0] - pts[k - 1][0])
        y = pts[k - 1][1] + t * (pts[k][1] - pts[k - 1][1])
        out.append((x, y))
    return out


def nearest_point_on_graph(x, y, G: nx.Graph):
    best = None
    best_d = 1e18
    for a, b in G.edges():
        ax, ay = G.nodes[a]["east"], G.nodes[a]["north"]
        bx, by = G.nodes[b]["east"], G.nodes[b]["north"]
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        t = 0 if L2 == 0 else max(0, min(1, ((x - ax) * dx + (y - ay) * dy) / L2))
        px, py = ax + t * dx, ay + t * dy
        d = math.hypot(x - px, y - py)
        if d < best_d:
            best_d = d
            best = (px, py, a, b, t)
    return best, best_d


def subgraph_near_stroke(G: nx.Graph, pts: list[tuple[float, float]], buffer_m: float) -> nx.Graph:
    line = LineString(pts) if len(pts) >= 2 else Point(pts[0]).buffer(buffer_m)
    keep_nodes = set()
    for nid, data in G.nodes(data=True):
        if line.distance(Point(data["east"], data["north"])) <= buffer_m:
            keep_nodes.add(nid)
    return G.subgraph(keep_nodes).copy()


def route_stroke(G: nx.Graph, src_osm, tgt_osm, sketch_pts, buffer_m):
    sub = subgraph_near_stroke(G, sketch_pts, buffer_m)
    if src_osm not in sub or tgt_osm not in sub:
        return None, None
    try:
        path = nx.shortest_path(sub, src_osm, tgt_osm, weight="length")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None, None
    coords = [(sub.nodes[n]["east"], sub.nodes[n]["north"]) for n in path]
    length = polyline_length(coords)
    eu = math.hypot(sketch_pts[0][0] - sketch_pts[-1][0], sketch_pts[0][1] - sketch_pts[-1][1])
    ratio = length / eu if eu > 1 else 999
    return coords, ratio


def build_kmz(nodes_out, edges_out, by_id):
    def pm_point(n, name):
        return f"""    <Placemark>
      <name>{xml(name)}</name>
      <Point><coordinates>{n['lon']},{n['lat']},0</coordinates></Point>
    </Placemark>"""

    def xml(s):
        return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    landmarks, juncs, unmatched_lines, matched_lines = [], [], [], []
    for n in nodes_out:
        kind = n.get("node_kind") or ""
        name = n.get("landmark_name") or n.get("Label") or n["Id"]
        if kind == "marker":
            lid = n.get("landmark_id") or ""
            landmarks.append(pm_point(n, f"{lid} {name}".strip()))
        elif n.get("snap_status", "").startswith("junction"):
            juncs.append(pm_point(n, f"#{n['Id']} {n.get('snap_status')}"))

    for e in edges_out:
        wkt = e.get("wkt") or ""
        status = e.get("snap_status") or "unmatched"
        coords = ""
        if wkt.startswith("LINESTRING"):
            inner = wkt[len("LINESTRING") :].strip().strip("()")
            pts = []
            for part in inner.split(","):
                x, y = part.strip().split()[:2]
                lon, lat = TO_LL.transform(float(x), float(y))
                pts.append(f"{lon:.7f},{lat:.7f},0")
            coords = " ".join(pts)
        else:
            a, b = by_id.get(int(e["Source"])), by_id.get(int(e["Target"]))
            if not a or not b:
                continue
            coords = f"{a['lon']},{a['lat']},0 {b['lon']},{b['lat']},0"
        style = "#ok" if status == "snapped" else "#bad"
        folder = matched_lines if status == "snapped" else unmatched_lines
        folder.append(
            f"""    <Placemark>
      <name>e{e['Id']} {status}</name>
      <styleUrl>{style}</styleUrl>
      <LineString><tessellate>1</tessellate><coordinates>{coords}</coordinates></LineString>
    </Placemark>"""
        )

    kml = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
  <name>Kowel snapped to OSM</name>
  <Style id="ok"><LineStyle><color>ff2ecc71</color><width>3</width></LineStyle></Style>
  <Style id="bad"><LineStyle><color>ff0000ff</color><width>3</width></LineStyle></Style>
  <LookAt><longitude>24.7087</longitude><latitude>51.2153</latitude><range>6500</range></LookAt>
  <Folder><name>landmarks ({len(landmarks)})</name>
{chr(10).join(landmarks)}
  </Folder>
  <Folder><name>matched junctions ({len(juncs)})</name>
{chr(10).join(juncs)}
  </Folder>
  <Folder><name>snapped streets ({len(matched_lines)})</name>
{chr(10).join(matched_lines)}
  </Folder>
  <Folder><name>UNMATCHED streets — review ({len(unmatched_lines)})</name>
{chr(10).join(unmatched_lines)}
  </Folder>
</Document>
</kml>
"""
    with zipfile.ZipFile(OUT_KMZ, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("doc.kml", kml)


def main() -> None:
    nodes = load_csv(NODES_IN)
    edges = load_csv(EDGES_IN)
    by_id, adj, deg = schematic_graph(nodes, edges)

    pos = {}
    for i, n in by_id.items():
        e, nv = TO_UTM.transform(float(n["lon"]), float(n["lat"]))
        pos[i] = [e, nv]

    lats = [float(n["lat"]) for n in nodes]
    lons = [float(n["lon"]) for n in nodes]
    pad = 0.006
    payload = fetch_osm(min(lats) - pad, min(lons) - pad, max(lats) + pad, max(lons) + pad)
    G = build_osm_graph(payload)
    print(f"OSM graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    osm_junc = {}
    for nid, data in G.nodes(data=True):
        d = G.degree(nid)
        if d == 2:
            continue
        br = []
        x, y = data["east"], data["north"]
        for nb in G.neighbors(nid):
            br.append(math.atan2(G.nodes[nb]["north"] - y, G.nodes[nb]["east"] - x))
        osm_junc[nid] = {**data, "deg": d, "bearings": br}
    print(f"OSM junctions/dead-ends: {len(osm_junc)}")

    street_ids = [i for i, d in deg.items() if d >= 1]
    junc_ids = [i for i in street_ids if deg[i] >= 3]
    dead_ids = [i for i in street_ids if deg[i] == 1]
    print(f"schematic junctions={len(junc_ids)} deadends={len(dead_ids)} shape={sum(1 for i in street_ids if deg[i]==2)}")

    gcp_ids = [
        i for i, n in by_id.items()
        if n.get("node_kind") == "marker" and n.get("georef_role") == "gcp"
        and n.get("landmark_kind") == "building"
    ]

    match = {}
    for it in range(ICP_ITERS):
        t = it / max(1, ICP_ITERS - 1)
        radius = START_RADIUS * (1 - t) + END_RADIUS * t
        match = match_junctions(junc_ids + dead_ids, pos, deg, adj, osm_junc, radius)
        ctrl_src, ctrl_dst = [], []
        for uid, oid in match.items():
            ctrl_src.append(pos[uid])
            ctrl_dst.append([osm_junc[oid]["east"], osm_junc[oid]["north"]])
        for uid in gcp_ids:
            ctrl_src.append(pos[uid])
            ctrl_dst.append(pos[uid])  # landmarks stay
        src = np.array(ctrl_src, float)
        dst = np.array(ctrl_dst, float)
        query_ids = [i for i in street_ids if i not in match]
        if query_ids:
            q = np.array([pos[i] for i in query_ids], float)
            q2 = fit_tps(src, dst, q, TPS_SMOOTH)
            for i, xy in zip(query_ids, q2):
                pos[i] = [float(xy[0]), float(xy[1])]
        # snap matched exactly onto OSM nodes
        for uid, oid in match.items():
            pos[uid] = [osm_junc[oid]["east"], osm_junc[oid]["north"]]
        print(f"  ICP {it+1}: radius={radius:.0f}m  matched={len(match)}/{len(junc_ids)+len(dead_ids)}")

    # Snap unmatched street nodes onto nearest OSM edge (soft, keeps topology)
    for uid in street_ids:
        if uid in match:
            continue
        hit, d = nearest_point_on_graph(pos[uid][0], pos[uid][1], G)
        if hit and d < 80:
            pos[uid] = [hit[0], hit[1]]

    paths = strokes_from(adj, deg, list(by_id))
    edge_geom = {}  # (s,t) frozen -> list of utm coords
    edge_meta = {}
    snapped_strokes = 0
    unmatched_strokes = 0

    for path in paths:
        sketch = [tuple(pos[i]) for i in path if i in pos]
        if len(sketch) < 2:
            continue
        u, w = path[0], path[-1]
        src_osm, tgt_osm = match.get(u), match.get(w)

        def nearest_osm(nid, graph):
            x, y = pos[nid]
            best, best_d = None, 1e18
            for osm_id, data in graph.nodes(data=True):
                d = math.hypot(x - data["east"], y - data["north"])
                if d < best_d:
                    best, best_d = osm_id, d
            return best if best_d <= 70 else None

        coords, ratio = None, None
        if src_osm is None or tgt_osm is None:
            sub_guess = subgraph_near_stroke(G, sketch, STROKE_BUFFER)
            if src_osm is None:
                src_osm = nearest_osm(u, sub_guess)
            if tgt_osm is None:
                tgt_osm = nearest_osm(w, sub_guess)
        if src_osm is not None and tgt_osm is not None and src_osm != tgt_osm:
            coords, ratio = route_stroke(G, src_osm, tgt_osm, sketch, STROKE_BUFFER)
            if coords is None or ratio is None or ratio > MAX_DETOUR:
                coords, ratio = route_stroke(G, src_osm, tgt_osm, sketch, STROKE_BUFFER * 1.8)
        status = "snapped"
        if coords is None or ratio is None or ratio > MAX_DETOUR:
            coords = sketch
            status = "unmatched"
            unmatched_strokes += 1
        else:
            snapped_strokes += 1
            # place interior nodes along the OSM path by schematic arc-length fraction
            sk_len = polyline_length(sketch) or 1.0
            acc = 0.0
            fracs = [0.0]
            for a, b in zip(sketch, sketch[1:]):
                acc += math.hypot(b[0] - a[0], b[1] - a[1])
                fracs.append(acc / sk_len)
            placed = interpolate_along(coords, fracs)
            for nid, xy in zip(path, placed):
                pos[nid] = [xy[0], xy[1]]

        # per original edge along this stroke
        for a, b in zip(path, path[1:]):
            edge_geom[frozenset((a, b))] = coords if status == "snapped" else [tuple(pos[a]), tuple(pos[b])]
            edge_meta[frozenset((a, b))] = {
                "snap_status": status,
                "detour_ratio": "" if ratio is None else f"{ratio:.3f}",
            }

    print(f"strokes snapped={snapped_strokes} unmatched={unmatched_strokes} total={len(paths)}")

    # write nodes
    fieldnames = list(nodes[0].keys())
    for extra in ("snap_status", "snap_osm_node", "snap_dist_m"):
        if extra not in fieldnames:
            fieldnames.append(extra)
    nodes_out = []
    snap_dists = []
    for n in nodes:
        nid = int(n["Id"])
        row = dict(n)
        e, nv = pos[nid]
        lon, lat = TO_LL.transform(e, nv)
        # landmarks: keep original coords
        if n.get("node_kind") == "marker":
            row["snap_status"] = "landmark_anchor"
            row["snap_osm_node"] = ""
            row["snap_dist_m"] = ""
        else:
            old_e, old_n = TO_UTM.transform(float(n["lon"]), float(n["lat"]))
            d = math.hypot(e - old_e, nv - old_n)
            snap_dists.append(d)
            if nid in match:
                row["snap_status"] = "junction_matched" if deg[nid] >= 3 else "deadend_matched"
                row["snap_osm_node"] = str(match[nid])
            else:
                row["snap_status"] = "edge_projected"
                row["snap_osm_node"] = ""
            row["snap_dist_m"] = f"{d:.1f}"
            row["lon"] = f"{lon:.7f}"
            row["lat"] = f"{lat:.7f}"
            row["utm_easting"] = f"{e:.2f}"
            row["utm_northing"] = f"{nv:.2f}"
        nodes_out.append(row)

    write_csv(OUT_NODES, nodes_out, fieldnames)

    by_out = {int(r["Id"]): r for r in nodes_out}
    edges_out = []
    for e in edges:
        s, t = int(e["Source"]), int(e["Target"])
        meta = edge_meta.get(frozenset((s, t)), {"snap_status": "unmatched", "detour_ratio": ""})
        geom = edge_geom.get(frozenset((s, t)))
        wkt = ""
        if geom and len(geom) >= 2:
            wkt = "LINESTRING (" + ", ".join(f"{p[0]:.2f} {p[1]:.2f}" for p in geom) + ")"
        row = dict(e)
        row["snap_status"] = meta["snap_status"]
        row["detour_ratio"] = meta["detour_ratio"]
        row["wkt"] = wkt
        edges_out.append(row)
    write_csv(OUT_EDGES, edges_out, list(edges[0].keys()) + ["snap_status", "detour_ratio", "wkt"])

    build_kmz(nodes_out, edges_out, by_out)

    junc_matched = sum(1 for i in junc_ids if i in match)
    print(f"wrote {OUT_NODES}")
    print(f"wrote {OUT_EDGES}")
    print(f"wrote {OUT_KMZ}")
    print(f"junctions matched {junc_matched}/{len(junc_ids)}")
    if snap_dists:
        arr = np.array(snap_dists)
        print(f"street-node move vs TPS: median {np.median(arr):.1f} m  p90 {np.percentile(arr,90):.1f} m  max {arr.max():.1f} m")

    # landmark drift check
    for lid in ("A1", "D4", "M6", "F1"):
        rows = [r for r in nodes_out if r.get("landmark_id") == lid]
        for r in rows:
            orig = by_id[int(r["Id"])]
            d = haversine_m(float(orig["lat"]), float(orig["lon"]), float(r["lat"]), float(r["lon"]))
            print(f"  landmark {lid} drift {d:.2f} m  ({r.get('snap_status')})")


if __name__ == "__main__":
    main()
