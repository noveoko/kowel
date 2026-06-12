# Addendum A — QGIS Integration & Multi-Temporal Aerials

**Applies to:** Kowel 1939 Archive Explorer spec (v2)
**Changes:** storage format, spatial workflow, new temporal-evidence model, revised milestones
**New inputs:** 7 georeferenced aerial photos (1915–1944), ~12 city maps (19th c.–1940s)

---

## A1. Decision: GeoPackage as the single shared database

Replace `archive.sqlite` with **`kowel.gpkg`**. Rationale, step by step:

1. A GeoPackage is physically a SQLite database with a standardized spatial schema on top. Everything in the v2 spec that assumed SQLite (plain tables, transactions, one-file backup, `sqlite3` stdlib access) carries over unchanged.
2. QGIS reads and *edits* GeoPackage layers natively — no import/export, no plugin needed. Building footprints and camera poses become ordinary QGIS vector layers.
3. The Python tool opens the same file with `sqlite3` (non-spatial tables) and `pyogrio`/`fiona` or plain SQL (spatial tables — GPKG geometry is just a BLOB column with a documented encoding; for writing geometries, use `geopandas.to_file(..., driver="GPKG")` or GDAL).
4. Result: one file is the whole project state. Back up by copying. No server, no sync logic.

**Concurrency rule (important):** SQLite allows one writer at a time, and QGIS holds write locks while a layer is in edit mode. Convention: don't run tool *write* operations (ingest/enrich/confirm) while a QGIS edit session is open on `kowel.gpkg`. Reads are safe. The tool checks for and warns about lock conflicts (`PRAGMA busy_timeout`, clear error message). In practice with one user this is a non-issue, but it must be documented, not discovered.

### Revised schema (deltas only)

```
-- spatial layers (QGIS-editable):
buildings        footprint POLYGON, name, address_1939, status_1939, notes…
camera_poses     POINT, photo_id, direction_deg, fov_guess, confidence
map_annotations  POINT/LINE/POLYGON, free sketch layer for research notes

-- new non-spatial tables:
rasters          id, kind (aerial|map), year, year_confidence, path,
                 georef_quality_note          ← registry of your 7+12 rasters
building_states  building_id, raster_id, state
                 (present|absent|changed|unclear|not_covered), note,
                 confirmed_by, confirmed_at   ← the temporal evidence grid (§A3)
```

All v2 tables (`photos`, `observations`, `tags`, `attributes`, `embeddings`, `pair_checks`, `directory_1929`, `collections`) remain as non-spatial GPKG tables.

---

## A2. Division of labor: QGIS vs. the tool

**Challenged assumption: "build it on top of QGIS."** Partly yes, partly no:

- *Yes* for everything spatial — that's mature, free functionality you shouldn't rebuild: layer management for 19 rasters, footprint digitizing, snapping, spatial queries, styling, print layouts.
- *No* for the photo workflows. Two hard constraints: (1) QGIS ships its own Python interpreter; installing torch/SigLIP/LightGlue into it is fragile and breaks on QGIS upgrades — ML must live in its own venv; (2) the highest-leverage screens (review queue, search grid, crop-to-search) are slow to build well in Qt but fast as a local web page.

| Task | Where | Notes |
|---|---|---|
| Georeference remaining maps | QGIS Georeferencer | One-time; aerials already done |
| Digitize building footprints | QGIS | Over the reference aerial (§A3.1) |
| Edit building attributes spatially | QGIS attribute forms | Same table the tool reads |
| Place/adjust camera poses | QGIS (point + rotation field) | Tool can propose; QGIS refines. Style arrows by `direction_deg` |
| Temporal state review | Tool web UI (primary) | Side-by-side raster flipper, §A3.2; QGIS alternative: layer toggling |
| Ingest/enrich/search/review/link/verify | Tool (CLI + web UI) | Own venv, torch allowed |
| Coverage & evidence maps | QGIS (graduated styling on SQL views) | Tool maintains `v_building_evidence` view |
| Dossier export | Tool | Now includes per-building map/aerial crops via rasterio |
| "Photos for selected feature" panel | Thin QGIS plugin, **M6, optional** | ~200 lines: selection → HTTP GET to local API → thumbnail panel. No ML inside QGIS |

The plugin is deliberately last: the GeoPackage already gives 90% of the integration for 0% of the maintenance burden.

---

## A3. Multi-temporal aerials: establishing the 1939 baseline

This is the addendum's biggest substantive addition. Seven dated aerials spanning 1915–1944 let you *bracket* summer 1939 per building — which is exactly the historical claim your model makes.

### A3.1 Reference frame

1. Pick the **reference aerial**: the sharpest, best-georeferenced one closest to 1939 (a 1944 German recon image is typical and fine — WWII damage is handled by the state grid, not by avoiding the raster).
2. Digitize footprints **once**, over the reference aerial only. Don't redraw per epoch — that multiplies work and creates identity-matching problems. One footprint = one building identity through time; geometry changes (extensions, demolition) are recorded as *states*, with `map_annotations` sketches when shape detail matters.
3. Load the ~12 historical maps as additional layers. Where a map contradicts the aerials (cartographic generalization is common), aerials win for geometry; maps win for names, addresses, and plot boundaries.

### A3.2 The state grid

For each building × each dated raster, record one of `present / absent / changed / unclear / not_covered`. That's potentially (buildings × 7) judgments, so the workflow must be cheap per judgment:

- Tool web UI: building list on the left; main pane shows the same map extent cropped from each aerial in a row (rasterio window reads); keyboard `1–5` sets the state, auto-advance to next building. Realistic pace: several hundred judgments/hour. Do it opportunistically per neighborhood, not as a forced march.
- Derived verdict for 1939, computed not hand-set: present in nearest pre-1939 raster **and** in nearest post-1939 raster → `standing_1939 (bracketed)`; present before but absent after → `uncertain — destroyed between YYYY and YYYY` (war damage vs. pre-war demolition needs photo/document evidence); only post-war evidence → flag for research. The dossier prints this chain of reasoning, so the 3D model's per-building confidence is auditable.

### A3.3 What the aerials do *not* do

Reiterating the v1 autopsy: no pixel matching between aerials and street photos. The aerials' role is (a) footprint geometry, (b) roof form hints (oblique shots especially), (c) the temporal grid, (d) the canvas for camera-pose placement. Street-photo↔building linking still happens through the human-confirmed similarity/verification flow.

---

## A4. Camera poses, assisted

Placing ~1,000 camera positions manually is tedious; full automation is impossible. Middle path:

1. When you link a photo to buildings (v2 §4.4), the tool proposes a pose: position = centroid of viewpoints consistent with the linked buildings' footprints (e.g., if the photo shows buildings A and B with A left of B, the half-plane is constrained); direction = toward the linked buildings' centroid. Crude but a 10× head start.
2. You drag/rotate the point in QGIS (or a small map widget in the web UI) to refine.
3. `confidence` field: `exact / street-level / block-level / guess`. Coverage maps can then weight by confidence.

---

## A5. Revised milestones

1. **M0 — Spatial foundation (1–2 d, mostly QGIS, no code):** assemble `kowel.gpkg`; register all 19 rasters in `rasters` (with year + georef quality); georeference any maps still lacking it; choose reference aerial; digitize a pilot area (~50 buildings) to validate the schema before mass digitizing.
2. **M1 — Ingest + browser** (as v2).
3. **M2 — Search/embeddings** (as v2).
4. **M3 — Review, linking, building registry** (as v2; registry now = the GPKG footprint layer + 1929 directory import).
5. **M4 — Temporal grid + poses (3–4 d):** raster-flipper state UI, derived 1939 verdicts, assisted pose proposals, coverage SQL views + QGIS styling.
6. **M5 — Dossiers & export:** now including per-building crops from every aerial/map (a building's full cartographic biography on one page).
7. **M6 (optional) — QGIS thumbnail-panel plugin.**

## A6. New open questions

1. Which aerial is the georeferencing *anchor* — were all 7 rectified independently, or to a common base? Independent georeferencing means footprints will misalign by a few meters across epochs; if so, the state-grid UI should allow a per-raster nudge offset rather than pretending alignment is perfect.
2. Aerial resolution: can you distinguish individual roofs in the 1915-era images, or only blocks? Determines whether `building_states` is realistic for early rasters or should be recorded at block level for them.
3. Rough building count inside the 1939 city limits (500? 3,000?) — sets the digitizing budget and whether the pilot area approach needs to become neighborhood-by-neighborhood permanently.
