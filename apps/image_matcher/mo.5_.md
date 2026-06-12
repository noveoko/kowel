Marcin, here’s a professional follow-up spec for M0.5 — Coregistration Pipeline, designed to stay deliberately independent from kowel.gpkg and the QGIS workflow. This module is essentially a computer vision + geospatial preprocessing tool that takes raw historical aerials and outputs georeferenced rasters aligned to your M0 reference aerial.


---

M0.5 — Coregister Remaining Aerials

Objective

Chain-register the remaining 6 aerial photographs to the already georeferenced reference aerial produced in M0.

This module:

does not depend on database state

does not depend on QGIS project files

requires only:

GDAL

LightGlue

Python runtime



Output:

6 georeferenced GeoTIFFs

transformation metadata

match quality reports

failure list for manual intervention


Maps/drawings that are not true aerial photographs are excluded from automation and manually georeferenced in QGIS using TPS.


---

Why M0.5 Exists Separately

M1 will focus on:

mass digitization

schema expansion

historical attribution


Those tasks need stable raster alignment.

M0.5 solves only:

raw historical aerial → aligned raster

This separation gives:

Parallel development

You can build M0.5 before M1.

Reduced complexity

No geopackage coupling.

Better testing

Computer vision pipeline can be unit-tested independently.


---

Inputs

Input directory:

coregister/
├── reference/
│   └── ref_1944.tif
│
├── aerials/
│   ├── img_01.tif
│   ├── img_02.tif
│   └── ...
│
└── output/


---

Required Input Files

Reference raster

Already georeferenced in M0.

Requirements:

GeoTIFF preferred

CRS embedded

reasonable warp quality

stable coverage of city


Example:

ref_1944.tif

Contains:

affine transform

CRS

spatial extent



---

Source aerials

6 remaining images:

Characteristics:

same region

partially overlapping

similar scale preferred

may contain:

rotation

translation

perspective distortion

lens distortion

film deformation




---

Processing Pipeline

Pipeline stages:

Load
 ↓
Preprocess
 ↓
Feature extraction
 ↓
Feature matching
 ↓
Outlier rejection
 ↓
Transform estimation
 ↓
Warp
 ↓
Quality scoring
 ↓
Export


---

Stage 1 — Preprocessing

Historical aerials often have poor contrast.

Normalize first.

Recommended preprocessing:


---

Convert to grayscale

If RGB:

Convert:

gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

Historical imagery usually gains nothing from color channels.


---

Contrast enhancement

Use CLAHE.

Why?

Improves:

roads

roof edges

shadows

rail tracks


Example:

clahe = cv2.createCLAHE(clipLimit=2.0)


---

Optional denoise

Only if scan noise is severe.

Avoid over-smoothing.

You need edges.


---

Stage 2 — Feature Detection

Traditional methods:

SIFT

ORB

AKAZE


Modern preferred:

LightGlue pipeline

Use:

SuperPoint + LightGlue


or

SIFT + LightGlue adapter


[LightGlue repository](https://github.com/cvg/LightGlue?utm_source=chatgpt.com)

Advantages over classic matching:

robust under rotation

handles weak textures

works well on aerial imagery


Important for WWII photos.


---

Stage 3 — Feature Matching

Input:

reference keypoints

source keypoints


Output:

Matched pairs:

(x1, y1) ↔ (x2, y2)

Expected counts:

Good overlap:

500–5000 tentative matches


After filtering:

50–500 strong matches


Minimum viable:

> 20 good matches

Below that: manual workflow.


---

Stage 4 — Outlier Rejection

Critical.

Historical aerials produce false matches.

Use:

RANSAC

Estimate transform while rejecting outliers.

Example:

cv2.findHomography(..., cv2.RANSAC)

Reject matches from:

repeated roof patterns

rail sleepers

tree clusters


Quality metric:

Inlier ratio

Good:

> 0.4



Excellent:

> 0.7



Bad: < 0.2


---

Stage 5 — Transformation Model

Choose model based on distortion.


---

Case A — Similar aerials

Use affine transform.

Good for:

same sortie

similar altitude


Transformation:

rotation

scale

translation

shear


Fast and stable.


---

Case B — Perspective differences

Use homography.

Better if:

tilt differs

camera angle changed


Transformation matrix:

3x3

Recommended default.


---

Case C — Film warping

Use local warp.

Example:

thin plate spline

polynomial warp


Only if necessary.

Too flexible can overfit.


---

Chain Registration Strategy

This is the key design.

Do NOT always register directly to reference.

Use chaining.

Example:

Instead of:

A → REF
B → REF
C → REF

Sometimes better:

A → REF
B → A
C → B

Why?

Adjacent images often share:

similar scale

similar orientation

more overlap


This improves match reliability.


---

Graph Model

Treat aerials as graph.

Nodes:

images


Edges:

overlap confidence


Find best path to reference.

Example:

img_6 → img_4 → img_2 → ref

Professional approach: Use weighted graph search.

Weight based on:

overlap %

match count

inlier ratio



---

Stage 6 — Warp with GDAL

After transform estimation:

Warp source image into reference CRS.

Use GDAL.

Recommended:

gdalwarp

or Python bindings.

[GDAL documentation](https://gdal.org/en/stable/?utm_source=chatgpt.com)

Parameters:

preserve resolution

cubic resampling

same CRS as reference


Preferred resampling:

cubic

Avoid nearest-neighbor.


---

Stage 7 — Quality Metrics

Each output gets score.

Metrics:


---

Match count

Good:

>100


---

Inlier ratio

Good:

>0.4


---

Reprojection error

Excellent: < 3 px

Good: 3–8 px

Usable: 8–15 px


---

Coverage overlap

Measure:

How much overlaps reference?

Low overlap may still register but be unreliable.


---

Quality Classification

Score	Meaning

A	Production ready
B	Minor drift
C	Manual review
D	Failed


Example report:

{
  "image": "img_03.tif",
  "matches": 872,
  "inliers": 455,
  "inlier_ratio": 0.52,
  "reprojection_error_px": 4.3,
  "quality": "A"
}


---

Failure Detection

Automatic fail if:

matches < 20

inlier ratio < 0.15

warp unstable

reprojection error > 20 px


Mark:

MANUAL_QGIS_REQUIRED


---

Manual Fallback

Not all historical rasters are photos.

Examples:

drawn maps

military sketches

hand-annotated scans


Automation often fails.

Fallback:

Use QGIS.

Georeference manually with:

Thin Plate Spline (TPS)

Best for:

paper distortions

fold damage

scanned maps


Use many GCPs:

Recommended:

25–80 GCPs

Use stable landmarks:

roads

churches

bridges

rail junctions



---

Script Architecture

Recommended Python layout:

coregister/
├── main.py
├── matcher.py
├── warp.py
├── quality.py
├── graph.py
└── utils.py


---

Module Responsibilities

matcher.py

Handles:

preprocessing

feature extraction

LightGlue matching



---

graph.py

Computes:

best chain path

overlap graph



---

warp.py

Handles:

transformation estimation

GDAL warping



---

quality.py

Computes:

match statistics

classification



---

CLI Design

Example usage:

python main.py \
  --reference reference/ref_1944.tif \
  --input aerials/ \
  --output output/

Optional:

--min-matches 40
--min-inlier-ratio 0.3
--save-debug


---

Deliverables

By completion of M0.5:

[ ] 6 aerials processed

[ ] aligned GeoTIFF outputs

[ ] JSON quality reports

[ ] debug visualizations of matches

[ ] failures identified

[ ] non-photo maps routed to manual TPS workflow



---

Professional Notes for Historical Aerials

1. Expect partial automation

For 80-year-old imagery:

100% automation is unrealistic.

Typical success rate:

60–90% for true aerials

poor for hand-drawn maps



---

2. Rail infrastructure is extremely useful

In Kovel, rail geometry is likely the strongest matching feature.

Use it heavily.


---

3. Prefer local registration over global registration

Old scans often have:

nonlinear shrinkage

paper warping

lens deformation


Local accuracy matters more than perfect global alignment.


---

This gives you a clean pre-M1 pipeline:

M0: establish spatial truth
M0.5: align remaining imagery automatically
M1: digitize at scale and build historical GIS intelligence