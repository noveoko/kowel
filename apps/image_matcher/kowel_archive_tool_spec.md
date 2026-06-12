# Kowel 1939 Archive Explorer — Specification

**Project:** Photo evidence-management and exploration tool supporting the 3D reconstruction of Kowel as of summer 1939
**Status:** Draft v2 (supersedes the standalone image-matcher spec; the matcher survives as a component, §4.4)
**Corpus:** ~1,000 era photographs (scans; mostly B/W, varied quality), period maps, 1929 business directory

---

## 1. Reframing: from "image matcher" to "reconstruction evidence system"

### 1.1 The chain of reasoning, step by step

1. The end product is a historically accurate 3D model of the city. With ~1,000 sparse, degraded photos spread across a whole city, automated photogrammetry of the city is impossible (you need dozens of overlapping views per structure). Therefore the model will be built **building by building, by hand (Blender), guided by evidence**.
2. If the unit of reconstruction work is the *building*, the database must be **building-centric**, not photo-centric. The question the tool must answer daily is not "what's in this photo?" but "**what do I know about building X, and which photos prove it?**"
3. Buildings only mean something if they're pinned to space. So the **georeferenced 1939 street/cadastral map is the spine of the entire system**. Every building gets a footprint or point on it; every photo eventually gets an estimated camera position and view direction on it. Your repo's 1929 business directory is a bootstrap building registry (addresses, owners, business types) — import it on day one.
4. Searching/tagging 1,000 degraded scans by hand is the bottleneck you named. Modern zero-shot models solve the *recall* problem (find candidates fast) but not the *truth* problem (their tags are wrong too often for a historical record). Hence the core design rule: **AI proposes, the human confirms, the DB stores only confirmed facts — each with provenance** (`source: human | ai-confirmed`, model name, date).
5. 1,000 images is a small corpus. Everything fits in **one SQLite file + one image folder**; brute-force numpy cosine search over 1,000 embeddings takes ~1 ms. Any architecture beyond "local folder + local web page" is self-sabotage.

### 1.2 Assumptions challenged

| Assumption | Verdict |
|---|---|
| "I need a better image matcher" | The matcher is one verification feature. You need an evidence system: registry + links + search + dossiers. |
| "Auto-tagging will organize the archive" | Auto-tags on 1939 scans are search aids, not facts. Human-in-the-loop or the database rots. |
| "Searching needs a tag taxonomy (buildings, weather events…)" | Mostly no. Open-vocabulary embedding search ("flooded street", "thatched roof", "funeral procession") covers ad-hoc queries without maintaining a taxonomy. Keep a *small* controlled vocabulary only for facts that drive reconstruction (building type, material, storeys, roof form, condition). |
| "Build vs. use Tropy/digiKam" | Existing tools lack embedding search, geometric same-building verification, and 1939-map pinning. Build the thin custom layer; store everything in open formats (SQLite/JSON/files) so export to anything stays trivial. |
| "More automation = faster" | The scarce resource is your confirmation time. Optimize the *review UI* (keyboard-driven, batch confirm) before adding more AI. |

---

## 2. Product definition

### 2.1 Core questions the tool must answer

1. **Find:** "Show me photos containing X" — by text, by visual similarity to a chosen photo/crop, by tag, by map area, or combinations.
2. **Link:** "These 7 photos show the same building" — proposed by AI similarity, *verified* geometrically, confirmed by you.
3. **Dossier:** "Everything known about building #214 (Warszawska 12)": photos by facade/angle, confirmed attributes, directory entries, notes, sketches — exportable as a folder for the Blender session.
4. **Coverage:** "Which map areas/buildings have zero or weak photo evidence?" — drives archive hunting priorities and tells you where reconstruction must rely on typology instead of photos.
5. **Date/season:** "Is this photo plausibly ≤ summer 1939, and what season?" — foliage, snow, signage, vehicles as cues; stored as a confidence judgment, since the model must reflect *1939*, not 1925 or 1942.

### 2.2 Non-goals

- City-scale automated photogrammetry; any 3D modeling inside the tool (Blender's job).
- Cloud anything, multi-user sync, mobile app.
- Pixel-level aerial↔street correspondence (still out of scope, per v1 autopsy).
- Perfect automatic geolocation of photos — the tool assists, you place the pin.

---

## 3. Data model (SQLite, one file)

```
photos        id, file_hash, path, width, height, scan_source, rights,
              date_estimate (range), season, quality_notes, added_at
buildings     id, name, address_1939, lat, lon (or map x,y), footprint_geojson,
              status (standing_1939/unknown/demolished_pre1939), notes
observations  photo_id, building_id, facade (N/E/S/W/roof/interior),
              view (frontal/oblique/distant/detail), confirmed_by, confirmed_at
tags          photo_id, tag, source (human|ai_confirmed), model, confidence
attributes    building_id, key (storeys/material/roof_form/style/...),
              value, evidence_photo_id, note          ← facts WITH evidence links
camera_poses  photo_id, x, y, direction_deg, fov_guess, confidence
directory_1929 building_id?, raw_row…                  ← imported CSV, linkable
embeddings    photo_id, model, vector BLOB             ← siglip + dinov2
pair_checks   photo_a, photo_b, inliers, verdict, engine, checked_at
collections   id, name; collection_photos(...)         ← ad-hoc working sets
```

Design notes, briefly: `attributes` requiring an `evidence_photo_id` enforces the historiographic discipline that every modeled fact traces to a source. `pair_checks` caches geometric verification so the expensive step never reruns. Everything exports to JSON/CSV with one command.

---

## 4. System components

```
kowel-archive/
├── data/                      # originals (read-only), derivatives/, thumbs/
├── archive.sqlite
├── src/kowel_archive/
│   ├── cli.py                 # ingest | enrich | serve | export | report
│   ├── db.py                  # schema, migrations (sqlite3 stdlib)
│   ├── ingest.py              # §4.1
│   ├── enrich/
│   │   ├── embed_siglip.py    # text+image embeddings (search)
│   │   ├── embed_dino.py      # instance similarity (same-building)
│   │   ├── suggest_tags.py    # zero-shot tag proposals
│   │   └── ocr.py             # optional: signage OCR (PL/RU/YI), §4.2
│   ├── match/                 # the v1-spec matcher, slimmed:
│   │   ├── engine.py          # SuperPoint+LightGlue (or SIFT fallback)
│   │   └── verify.py          # MAGSAC + inlier verdict (same thresholds)
│   ├── search.py              # text→image, image→image, filters
│   ├── webapp/                # FastAPI + one HTML page (vanilla JS + Leaflet)
│   └── export.py              # building dossiers, full JSON dump
└── tests/
```

### 4.1 Ingest (CLI, run once + incrementally)

Step by step: (1) walk folder, SHA-256 each file, skip known hashes — re-running is always safe; (2) read dimensions/EXIF, build 512 px thumbnails and 1600 px working copies (originals never touched); (3) insert `photos` rows; (4) report duplicates (identical and near-duplicate via embedding distance > 0.98 — scans of the same print are common in gathered archives).

### 4.2 Enrichment (CLI, batched, resumable)

- **SigLIP embeddings** for every photo → enables free-text search and similarity. (SigLIP over CLIP: better zero-shot retrieval at the same size; runs CPU-fine at this scale, ~1–2 s/image.)
- **DINOv2 embeddings** → instance-level "more like this exact building" similarity, which is a different signal from semantic similarity.
- **Tag suggestions:** score each photo against a YAML-configurable prompt list ("wooden building", "brick building", "church", "market", "snow", "flood", "military", "horse cart", "shop signage"…). Stored as *suggestions* with confidence; they surface in the review UI and become `tags` rows only on confirmation.
- **OCR (optional, M4):** shop signs are geolocation gold — a legible "M. Goldberg" sign cross-referenced against the 1929 directory can pin a photo to an address. Modern OCR on degraded signage will be hit-or-miss; treat as suggestions, same rule as always.

### 4.3 Search & explore (web UI, localhost)

- **Grid browser** with instant filters (tags, linked/unlinked, date confidence, collection).
- **Text search** box → SigLIP text embedding → ranked grid. No taxonomy needed for ad-hoc queries.
- **"More like this"** on any photo (choose semantic/SigLIP or instance/DINOv2 mode). **Crop-to-search**: drag a box around an architectural detail and search on the crop — key for "find other photos with this window type/cornice".
- **Map view** (Leaflet, georeferenced 1939 map raster as overlay): building pins colored by evidence strength; click → dossier. Photo camera-pose arrows once placed.
- **Keyboard-first review queue:** AI suggestions stream one by one; `y/n/skip`, arrows to navigate. This screen determines whether the archive actually gets organized — it gets the most design attention.

### 4.4 Linking & verification (the old matcher's new job)

Flow: pick a photo → "find same building" → DINOv2 ranks candidates → for each candidate you accept as plausible, one click runs **geometric verification** (LightGlue + MAGSAC; verdicts and thresholds exactly as in the v1-replacement spec) → verified pairs propose an `observations` cluster → you assign the cluster to a building on the map (or create one). Result: photo↔building links with geometric evidence cached in `pair_checks`.

### 4.5 Dossiers & export

`kowel-archive export --building 214` → folder containing working copies sorted by facade, `dossier.md` (attributes + evidence links + directory entries + notes), and `dossier.json`. This folder is what you open next to Blender. Also: `export --all` full JSON/CSV dump (lock-in insurance), and `report coverage` → map heatmap + CSV of buildings ranked by evidence weakness (answers "where do I hunt for more photos / where must I rely on typology").

---

## 5. Technology choices

| Concern | Choice | Why |
|---|---|---|
| DB | SQLite (stdlib) | One file, transactional, queryable for decades. No server. |
| Vector search | numpy brute force | 1,000×768 floats ≈ 3 MB; cosine top-k in ~1 ms. FAISS would be pure overhead. |
| Embeddings | SigLIP (search) + DINOv2 ViT-S (instance) | Complementary signals; both CPU-viable here. |
| Pair verify | LightGlue + OpenCV MAGSAC | Per v1 autopsy; SIFT fallback retained. |
| Backend | FastAPI + uvicorn | Thin JSON API over the DB. |
| Frontend | Single HTML page, vanilla JS, Leaflet | No build step; a tool like this must still run in 10 years. |
| Map | Period map raster, georeferenced (QGIS one-time job), served as image overlay or local tiles | The spine (§1.1.3). |
| Packaging | `pyproject.toml`, `[deep]` extra for torch models | Core ingest/browse works without torch. |

## 6. Milestones (each ends in something you can use)

1. **M1 — Spine (2–3 d):** schema, ingest, thumbnails, grid browser with manual tags + collections. *Usable as a fast local photo browser immediately.*
2. **M2 — Search (2–3 d):** SigLIP + DINOv2 enrichment, text search, more-like-this, crop-to-search, duplicate report.
3. **M3 — Review & linking (3–4 d):** suggestion review queue, geometric verification, observations, building registry + 1929 directory import.
4. **M4 — Map (2–3 d):** georeferenced overlay, building pins, camera poses, coverage report. (+ optional OCR.)
5. **M5 — Dossiers & polish (2 d):** exports, backup command, docs.

Acceptance tests mirror each milestone, e.g. M2: querying "church" must rank known church photos in top-20; a crop of a known doorway must retrieve the other photo of the same doorway in top-10. M3: the synthetic-homography and negative-control tests from the v1 spec, plus end-to-end link flow on a fixture set.

## 7. Open questions

1. Do you already have a georeferenced 1939 (or 1929/1936) map of Kowel, or is QGIS georeferencing a prerequisite task? It's the spine — worth doing first.
2. Rough split of the 1,000 photos: street scenes vs. portraits/groups vs. aerials? Portraits with background buildings are still evidence but may want a face-blur/ethics flag for any published outputs.
3. Are dates known for some photos (postcards with stamps, captions)? Even 50 anchored dates make the season/date estimation far more grounded.
4. Single machine or do collaborators exist? (Single: spec stands. Collaborators: still SQLite, but add export/merge rather than a server.)
