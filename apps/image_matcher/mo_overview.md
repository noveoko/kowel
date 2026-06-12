Marcin, here’s a professional GIS workflow for M0 — Spatial Foundation using QGIS and ~80-year-old aerial photos (likely WWII-era reconnaissance imagery). The goal is to create a robust base for downstream digitization and analysis while minimizing compounding georeferencing errors.


---

M0 Overview

Deliverables:

kowel.gpkg (master geopackage)

19 raster entries registered with metadata:

filename

year

source

scan resolution

georef status

georef quality score

notes


1 reference aerial accurately georeferenced to modern coordinates

Pilot vector dataset (~50 buildings)

Validated schema for large-scale digitization



---

Phase 1 — Project Setup (QGIS)

1. Create clean project structure

I’d organize like this:

kowel_project/
│
├── raw_rasters/
│   ├── 1939/
│   ├── 1941/
│   ├── 1944/
│
├── processed/
│   ├── georeferenced/
│   ├── warped/
│
├── vectors/
│
├── exports/
│
└── kowel.gpkg

Why?
Because you want raw scans immutable.

Never overwrite raw scans.


---

2. Choose CRS

Since Kovel is in Kovel, use:

Recommended working CRS

EPSG:32635 — WGS84 / UTM Zone 35N


or

EPSG:2180 if working with Polish military maps


I strongly recommend UTM for metric measurements.

In QGIS:

Project → Properties → CRS

Set:

EPSG:32635


---

Phase 2 — Build kowel.gpkg

In QGIS:

Database → DB Manager → Create Geopackage

Name:

kowel.gpkg

Create layers:


---

1. Buildings layer

Geometry:

Polygon


Fields:

Field	Type

id	Integer
source_raster	Text
year	Integer
building_type	Text
confidence	Integer
exists_today	Boolean
notes	Text



---

2. Raster catalog layer

Geometry:

No geometry (table)


Fields:

Field	Type

raster_id	Integer
filename	Text
year	Integer
source	Text
dpi	Integer
georef_status	Text
rmse_m	Real
quality_score	Integer
notes	Text


This is critical professionally—treat rasters like assets.


---

3. GCP layer

Optional but useful.

Geometry:

Point


Fields:

Field	Type

raster	Text
gcp_type	Text
residual	Real



---

Phase 3 — Register all 19 rasters

You said:

> register all 19 rasters in rasters (year + georef quality)



This means cataloging first, not georeferencing all.

For each raster:

Open properties:

Record:

filename

scan dimensions

estimated year

source archive

overlap with city center?

damage?

distortion?



---

Quality scoring system (professional)

Use 1–5.

5 — Excellent

Sharp

Minimal warping

Nadir view

High overlap with map


4 — Good

Minor distortion


3 — Usable

Moderate lens distortion

Some folds


2 — Poor

Strong perspective

Blur


1 — Bad

Hard to use


Example:

Raster	Year	Quality

RAF_1944_01	1944	5
Luftwaffe_1941_03	1941	3


Only one raster becomes the reference raster.


---

Phase 4 — Choose reference aerial

This is the most important decision.

Criteria:

Pick the aerial with:

Best geometry

Avoid:

oblique images

heavy tilt

edge distortion


Choose:

closest to vertical

city center visible

least blur



---

How to evaluate

Check:

Are roads recognizable?

Intersections visible?

River banks visible?

Rail lines visible?

Rail lines are gold.

In QGIS, compare with:

modern satellite

historical maps

cadastral maps



---

Phase 5 — Modern base map

Use at least 2 references.

Recommended:

[OpenStreetMap](https://www.openstreetmap.org?utm_source=chatgpt.com)

[Google Maps](https://maps.google.com?utm_source=chatgpt.com) (visual only)

wartime maps

cadastral maps if available


In QGIS install:

QuickMapServices

Add:

satellite

OSM



---

Phase 6 — Georeference reference aerial

Use QGIS Georeferencer.

Open:

Raster → Georeferencer

Load reference aerial.


---

Ground Control Point (GCP) strategy

This determines quality.

For 80-year-old photos:

Use stable features.

Best GCPs:

Excellent

churches

rail junctions

bridges

cemetery corners

road intersections unchanged today


Examples in Kovel might include:

church spires

rail station

river crossings


Avoid:

trees

fences

temporary structures



---

Number of GCPs

Minimum:

10


Professional:

25–60


Spread them:

BAD:

all in center

GOOD:

distributed across entire image

Especially corners.


---

Transformation model

For old aerials:

Try in this order:


---

1. Polynomial 1 (Affine)

Best if:

photo mostly flat

low distortion


Preserves geometry.

Start here.


---

2. Polynomial 2

Use if:

noticeable warping


Good for WWII aerials.


---

3. Thin Plate Spline

Use only if:

severe distortion

folds

scan deformation


Danger: Can overfit.


---

Resampling

Use:

Cubic

or

Lanczos

Avoid nearest-neighbor unless binary scans.


---

RMSE Threshold

Professional rule:

Excellent

< 3 m

Good

3–8 m

Acceptable for historical work

8–20 m

For 80-year-old imagery:

I’d accept:

< 15 meters

if distortion is unavoidable.

Record RMSE in raster catalog.


---

Phase 7 — Validate georeference

After warping:

Overlay on modern map.

Check:

Roads align?

River bends align?

Rail lines align?

Expect mismatch due to:

demolished buildings

wartime destruction

urban redevelopment


That’s normal.

You care about global consistency, not perfect pixel alignment.


---

Phase 8 — Pilot digitization (~50 buildings)

This is where you validate schema.

Create polygon layer:

buildings_pilot

Snapping: Enable.


---

Digitizing rules

Professional consistency matters.

Decide:

Rule 1

Trace roof footprint or wall footprint?

For aerials: Usually roof footprint.


---

Rule 2

How to handle shadows?

Ignore shadows.


---

Rule 3

Occlusion by trees?

If 70% visible: Digitize.

If 30% visible: Mark low confidence.


---

Confidence scoring

Use:

Score	Meaning

5	Certain
4	Likely
3	Partial
2	Weak
1	Guess


This matters later in ML or historical inference.


---

Recommended pilot sampling

Digitize from:

dense urban center

suburbs

industrial zone

damaged area


Why?

To stress-test schema.

You’ll discover missing fields.

Example:

Need fields like:

roof_shape

destroyed_after

visibility


Better to discover now than after 5,000 polygons.


---

Validation Questions

After 50 buildings ask:


---

Schema validity

Can every building fit?

If not, add fields.


---

Georeference validity

Do footprints drift systematically?

Example:

west side shifted 8m


That suggests bad warp.


---

Workflow speed

Measure:

Time per building.

Example:

1 minute each → 5000 buildings = 83 hours


Important for planning.


---

Professional Tips for 80-Year-Old Aerials

1. Scanned film shrinkage is real

Old negatives warp.

Even perfect GCPs cannot fully fix this.

Expect local distortions.


---

2. Use rail infrastructure as anchors

Rail corridors often survive decades.

In Kovel this is especially useful because Kovel historically was a major rail hub.


---

3. Don’t georeference all 19 yet

This is key.

You said:

> georeference only reference aerial



Correct.

Do NOT warp all 19 first.

Why?

Because later you can use:

photo-to-photo registration:

Raster 2 → Reference aerial
Raster 3 → Reference aerial
...

This reduces cumulative error.


---

Final M0 Checklist

By end of M0 you should have:

[ ] kowel.gpkg

[ ] CRS selected

[ ] 19 rasters cataloged

[ ] quality scores assigned

[ ] best aerial chosen

[ ] reference aerial georeferenced

[ ] RMSE recorded

[ ] 50 pilot buildings digitized

[ ] schema validated


That gives you a professional-grade historical GIS foundation for M1+.