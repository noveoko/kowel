"""Streamlit app: draw under a map street name → deskew → transform → OCR → top-10 matches."""

from __future__ import annotations

import io
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import streamlit as st
from streamlit_drawable_canvas import st_canvas

from geometry import (
    PrepTransforms,
    Viewport,
    apply_prep_transforms,
    band_to_fabric_rect,
    canvas_stroke_to_baseline,
    deskew_band,
    fabric_rect_to_baseline,
    make_viewport_image,
    ocr_variants,
    overlay_band,
    preprocess_for_ocr,
    translate_baseline,
)
from ca_ga_rank import rank_ca_ga
from map_nav import bounds_to_viewport, build_image_map, full_image_viewport
from ocr_rank import (
    build_allowlist,
    candidate_names,
    load_truth_table,
    rank_streets,
    rank_streets_multi,
    run_ocr,
    run_ocr_ensemble,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
MAX_CANVAS_WIDTH = 1100
MAX_CANVAS_HEIGHT = 900
NAV_WIDTH = 900
NAV_HEIGHT = 650


st.set_page_config(page_title="Kowel street-name OCR", layout="wide")
st.title("Kowel street-name OCR")
st.caption(
    "Navigate with the mouse wheel (zoom) and middle-mouse drag (pan), lock the view, "
    "draw a baseline under a street label, then transform + recognize."
)


def _init_state():
    defaults = {
        "baseline": None,
        "deskewed_raw": None,
        "deskewed_prep": None,
        "prep_rot90": 0,
        "prep_fine_deg": 0.0,
        "prep_flip_h": False,
        "prep_flip_v": False,
        "prep_invert": False,
        "ui_mode": "Navigate",  # Navigate | Draw
        "pending_ui_mode": None,  # applied before the radio widget on next run
        "locked_viewport": None,  # Viewport | None
        "nav_live_viewport": None,
        "nav_center": None,
        "nav_zoom": None,
        "nav_image_id": None,
        "draw_tool": "Draw baseline",
        "band_height_px": 36.0,
        "band_canvas_json": None,
        "band_seed_token": None,
        "ocr_text": "",
        "ocr_details": [],
        "ocr_readings": [],
        "top10": None,
        "ca_binary": None,
        "review_log": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _reset_transforms():
    st.session_state.prep_rot90 = 0
    st.session_state.prep_fine_deg = 0.0
    st.session_state.prep_flip_h = False
    st.session_state.prep_flip_v = False
    st.session_state.prep_invert = False


def _clear_selection():
    st.session_state.baseline = None
    st.session_state.deskewed_raw = None
    st.session_state.deskewed_prep = None
    st.session_state.ocr_text = ""
    st.session_state.ocr_details = []
    st.session_state.ocr_readings = []
    st.session_state.top10 = None
    st.session_state.ca_binary = None
    st.session_state.band_canvas_json = None
    st.session_state.band_seed_token = None
    _reset_transforms()


def _request_ui_mode(mode: str):
    """Queue a mode change for the next run (before the radio widget mounts)."""
    st.session_state.pending_ui_mode = mode


def _apply_pending_ui_mode():
    pending = st.session_state.get("pending_ui_mode")
    if pending in ("Navigate", "Draw"):
        st.session_state.ui_mode = pending
        st.session_state.pending_ui_mode = None


def _current_transforms() -> PrepTransforms:
    return PrepTransforms(
        rot90=int(st.session_state.prep_rot90) % 4,
        fine_deg=float(st.session_state.prep_fine_deg),
        flip_h=bool(st.session_state.prep_flip_h),
        flip_v=bool(st.session_state.prep_flip_v),
        invert=bool(st.session_state.prep_invert),
    )


_init_state()
_apply_pending_ui_mode()


@st.cache_data
def _cached_truth_table():
    return load_truth_table()


@st.cache_resource
def _cached_reader():
    import easyocr

    return easyocr.Reader(["pl", "en"], gpu=False)


def load_upload(upload) -> np.ndarray:
    data = np.frombuffer(upload.getvalue(), dtype=np.uint8)
    bgr = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError("Could not decode image")
    return bgr


with st.sidebar:
    st.header("1. Image")
    upload = st.file_uploader("Map image", type=["png", "jpg", "jpeg", "tif", "tiff", "webp"])
    st.subheader("Mode")
    st.radio(
        "Workspace",
        options=["Navigate", "Draw"],
        key="ui_mode",
        help="Navigate: wheel zoom + middle-button pan. Draw: lock a view, then draw the baseline.",
    )
    st.caption("Wheel = zoom · Middle-drag = pan · Left-drag = pan (Leaflet)")
    if st.button("Unlock view (back to Navigate)", use_container_width=True):
        st.session_state.locked_viewport = None
        _clear_selection()
        _request_ui_mode("Navigate")
        st.rerun()

    st.header("2. Band")
    band_height = st.slider(
        "Band height (px, full-res)",
        min_value=8,
        max_value=200,
        value=int(st.session_state.get("band_height_px", 36)),
        step=1,
        help="Initial height when creating the band. After you grab/resize the box, height follows the box.",
    )
    st.session_state.band_height_px = float(band_height)
    text_above = st.toggle("Text is above the baseline", value=True)
    nudge_x = st.slider("Nudge X (px)", min_value=-80, max_value=80, value=0, step=1)
    nudge_y = st.slider("Nudge Y (px)", min_value=-80, max_value=80, value=0, step=1)
    include_1917 = st.toggle("Include 1917 occupation names in candidates", value=False)
    st.header("3. Recognition")
    ranker_mode = st.selectbox(
        "Ranker",
        options=[
            "EasyOCR fuzzy",
            "CA+GA ink",
            "Blend both",
        ],
        help="CA+GA: cellular-automata ink cleanup + genetic search over the truth table. "
        "Best when letters are degraded and EasyOCR returns little.",
    )
    handwriting_mode = st.toggle(
        "Handwriting / low-quality mode",
        value=True,
        help="Runs OCR across several preprocessing renderings (denoise+sharpen, adaptive "
        "threshold, inverted) and ranks street names against every reading, keeping each "
        "candidate's best match. Slower than a single fixed pipeline, but far more forgiving "
        "of faint or degraded handwriting.",
    )
    min_conf = st.slider(
        "OCR confidence floor",
        min_value=0.0,
        max_value=0.9,
        value=0.15 if handwriting_mode else 0.3,
        step=0.05,
        help="Detected text below this is still kept as a last-resort fallback so you never "
        "silently get empty OCR text, but only text at/above it is treated as a solid reading.",
    )
    restrict_charset = st.toggle(
        "Restrict OCR to street-name alphabet",
        value=True,
        help="Limits EasyOCR's output characters to those that actually appear in the truth "
        "table (plus space/hyphen/period). Stops it from hallucinating stray digits or symbols "
        "on messy handwriting — usually a meaningful accuracy win for a closed candidate list.",
    )
    ca_steps = st.slider("CA cleanup steps", min_value=0, max_value=8, value=3, step=1)
    score_all = st.checkbox(
        "Score all candidates (skip GA)",
        value=False,
        help="Exhaustive fitness over the truth table; often stabler than GA for ~160 names.",
    )
    known_chars = st.text_input(
        "Known characters (optional)",
        value="",
        help="Letters you can read on the crop, e.g. pkw — boosts names containing them.",
    )
    run_btn = st.button("Run recognition", type="primary", use_container_width=True)
    if st.button("Clear baseline / results", use_container_width=True):
        _clear_selection()
        st.rerun()

if upload is None:
    st.info("Upload a map image to begin. Tip: use the **line** tool and draw under the street name.")
    sample = REPO_ROOT / "tutorials" / "streetname.PNG"
    if sample.exists():
        st.write(f"Sample image available at `{sample.relative_to(REPO_ROOT).as_posix()}`.")
    st.stop()

try:
    image_bgr = load_upload(upload)
except ValueError as exc:
    st.error(str(exc))
    st.stop()

img_h, img_w = image_bgr.shape[:2]
ui_mode = st.session_state.ui_mode

if ui_mode == "Navigate":
    st.subheader("Step 1 — Navigate map")
    st.write(
        "**Mouse wheel** zooms · **middle-mouse drag** pans (left-drag also pans). "
        "Frame the street name, then lock the view for drawing."
    )
    # Reset stored camera when a new image is uploaded
    image_id = f"{upload.name}:{img_w}x{img_h}:{len(upload.getvalue())}"
    if st.session_state.nav_image_id != image_id:
        st.session_state.nav_image_id = image_id
        st.session_state.nav_center = None
        st.session_state.nav_zoom = None
        st.session_state.nav_live_viewport = None
        st.session_state.locked_viewport = None

    fmap, nav_scale, nav_w, nav_h = build_image_map(
        image_bgr,
        width=NAV_WIDTH,
        height=NAV_HEIGHT,
        center=st.session_state.nav_center,
        zoom=st.session_state.nav_zoom,
    )
    from streamlit_folium import st_folium

    nav_kwargs = dict(
        width=NAV_WIDTH,
        height=NAV_HEIGHT,
        returned_objects=["bounds", "zoom", "center"],
        key=f"nav_{upload.name}_{nav_w}x{nav_h}",
    )
    if st.session_state.nav_center is not None:
        c = st.session_state.nav_center
        nav_kwargs["center"] = (c[0], c[1])
    if st.session_state.nav_zoom is not None:
        nav_kwargs["zoom"] = int(round(float(st.session_state.nav_zoom)))
    nav_out = st_folium(fmap, **nav_kwargs)
    live_vp = None
    if nav_out:
        if nav_out.get("center") is not None:
            c = nav_out["center"]
            if isinstance(c, dict):
                st.session_state.nav_center = [c.get("lat"), c.get("lng")]
            elif isinstance(c, (list, tuple)) and len(c) >= 2:
                st.session_state.nav_center = [c[0], c[1]]
        if nav_out.get("zoom") is not None:
            st.session_state.nav_zoom = float(nav_out["zoom"])
        if nav_out.get("bounds"):
            live_vp = bounds_to_viewport(
                nav_out["bounds"],
                nav_scale=nav_scale,
                img_w=img_w,
                img_h=img_h,
                max_w=MAX_CANVAS_WIDTH,
                max_h=MAX_CANVAS_HEIGHT,
            )
            st.session_state.nav_live_viewport = live_vp
    if live_vp is None:
        live_vp = st.session_state.nav_live_viewport

    if live_vp is not None:
        st.caption(
            f"Visible ≈ ({live_vp.x:.0f},{live_vp.y:.0f}) "
            f"{live_vp.w:.0f}×{live_vp.h:.0f}px full-res"
        )
    else:
        st.caption("Move/zoom the map once so bounds are reported.")

    lock_col1, lock_col2 = st.columns([1, 1])
    with lock_col1:
        if st.button("Lock view for drawing", type="primary", use_container_width=True):
            vp = live_vp or full_image_viewport(
                img_w, img_h, max_w=MAX_CANVAS_WIDTH, max_h=MAX_CANVAS_HEIGHT
            )
            st.session_state.locked_viewport = vp
            _clear_selection()
            _request_ui_mode("Draw")
            st.rerun()
    with lock_col2:
        if st.button("Lock whole map", use_container_width=True):
            st.session_state.locked_viewport = full_image_viewport(
                img_w, img_h, max_w=MAX_CANVAS_WIDTH, max_h=MAX_CANVAS_HEIGHT
            )
            _clear_selection()
            _request_ui_mode("Draw")
            st.rerun()

else:
    # Draw mode
    locked: Viewport | None = st.session_state.locked_viewport
    if locked is None:
        st.warning("No locked view — switching to Navigate.")
        _request_ui_mode("Navigate")
        st.rerun()

    pil_bg = make_viewport_image(image_bgr, locked)
    disp_w, disp_h = locked.disp_w, locked.disp_h
    scale_view = locked.scale
    origin_xy = (locked.x, locked.y)

    col_canvas, col_map = st.columns([1.4, 1])
    with col_canvas:
        st.subheader("Step 1 — Place the band")
        draw_tool = st.radio(
            "Tool",
            options=["Draw baseline", "Move band"],
            horizontal=True,
            key="draw_tool",
            help="Draw a line under the name, then switch to Move band to drag/resize/rotate the orange-green box.",
        )
        st.caption(
            f"Locked view origin ({locked.x:.0f}, {locked.y:.0f}) · "
            f"window {locked.w:.0f}×{locked.h:.0f}px · canvas {disp_w}×{disp_h}"
        )

        if draw_tool == "Draw baseline":
            st.write("Use the **line** tool: drag once under the street name along its reading direction.")
            canvas_key = (
                f"line_{upload.name}_{disp_w}x{disp_h}_"
                f"{locked.x:.1f}_{locked.y:.1f}_{locked.w:.1f}_{locked.h:.1f}"
            )
            canvas = st_canvas(
                fill_color="rgba(0,0,0,0)",
                stroke_width=3,
                stroke_color="#ff8c00",
                background_image=pil_bg,
                update_streamlit=True,
                height=disp_h,
                width=disp_w,
                drawing_mode="line",
                key=canvas_key,
                display_toolbar=True,
            )
            objects = []
            if canvas.json_data and canvas.json_data.get("objects"):
                objects = canvas.json_data["objects"]
            baseline = canvas_stroke_to_baseline(
                objects, scale=scale_view, origin_xy=origin_xy
            )
            if baseline is not None and baseline.length >= 2:
                if nudge_x or nudge_y:
                    baseline = translate_baseline(baseline, float(nudge_x), float(nudge_y))
                st.session_state.baseline = baseline
                # Reseed adjustable band from this baseline + slider height
                seed = (
                    f"{baseline.x1:.2f}:{baseline.y1:.2f}:{baseline.x2:.2f}:{baseline.y2:.2f}:"
                    f"{band_height}:{text_above}"
                )
                if st.session_state.band_seed_token != seed:
                    rect = band_to_fabric_rect(
                        baseline,
                        float(band_height),
                        scale=scale_view,
                        origin_xy=origin_xy,
                        text_above=text_above,
                    )
                    st.session_state.band_canvas_json = {
                        "version": "4.4.0",
                        "objects": [rect],
                    }
                    st.session_state.band_seed_token = seed
                    st.session_state.band_height_px = float(band_height)
                st.success(
                    f"Baseline {baseline.length:.0f}px · {baseline.angle_deg:.1f}° — "
                    f"switch to **Move band** to grab the box."
                )
            elif st.session_state.baseline is None:
                st.warning("No baseline yet — draw a line under the label.")

        else:
            # Move / transform band
            if st.session_state.baseline is None:
                st.warning("Draw a baseline first, then come back to Move band.")
            else:
                st.write(
                    "Click the green/orange box, then **drag** to move, use handles to "
                    "**resize**, or rotate. Left-drag empty space does nothing — grab the box."
                )
                if st.session_state.band_canvas_json is None:
                    rect = band_to_fabric_rect(
                        st.session_state.baseline,
                        float(st.session_state.band_height_px),
                        scale=scale_view,
                        origin_xy=origin_xy,
                        text_above=text_above,
                    )
                    st.session_state.band_canvas_json = {
                        "version": "4.4.0",
                        "objects": [rect],
                    }

                canvas = st_canvas(
                    fill_color="rgba(0, 220, 0, 0.25)",
                    stroke_width=2,
                    stroke_color="#ff8c00",
                    background_image=pil_bg,
                    update_streamlit=True,
                    height=disp_h,
                    width=disp_w,
                    drawing_mode="transform",
                    initial_drawing=st.session_state.band_canvas_json,
                    key=(
                        f"band_{upload.name}_{disp_w}x{disp_h}_"
                        f"{locked.x:.1f}_{locked.y:.1f}_{st.session_state.band_seed_token}"
                    ),
                    display_toolbar=True,
                )
                if canvas.json_data and canvas.json_data.get("objects"):
                    st.session_state.band_canvas_json = canvas.json_data
                    # Prefer named band rect; else last rect
                    rect_obj = None
                    for obj in canvas.json_data["objects"]:
                        if obj.get("type") == "rect":
                            rect_obj = obj
                            if obj.get("name") == "street_band":
                                break
                    parsed = (
                        fabric_rect_to_baseline(
                            rect_obj,
                            scale=scale_view,
                            origin_xy=origin_xy,
                            text_above=text_above,
                        )
                        if rect_obj
                        else None
                    )
                    if parsed is not None:
                        baseline, height_full = parsed
                        if nudge_x or nudge_y:
                            baseline = translate_baseline(
                                baseline, float(nudge_x), float(nudge_y)
                            )
                        st.session_state.baseline = baseline
                        st.session_state.band_height_px = max(2.0, float(height_full))
                        st.success(
                            f"Band placed · length {baseline.length:.0f}px · "
                            f"height {st.session_state.band_height_px:.0f}px · "
                            f"angle {baseline.angle_deg:.1f}°"
                        )

                if st.button("Reset band from baseline + height slider"):
                    st.session_state.band_seed_token = None
                    st.session_state.band_canvas_json = None
                    st.rerun()

    with col_map:
        st.subheader("Band preview")
        baseline = st.session_state.baseline
        height_eff = float(st.session_state.band_height_px)
        if baseline is None:
            st.info("Waiting for baseline…")
        else:
            try:
                result = deskew_band(
                    image_bgr,
                    baseline,
                    height=height_eff,
                    text_above=text_above,
                )
                st.session_state.deskewed_raw = result.image
                overlay = overlay_band(image_bgr, result.corners)
                xs = result.corners[:, 0]
                ys = result.corners[:, 1]
                pad = 40
                x0 = max(int(xs.min()) - pad, 0)
                y0 = max(int(ys.min()) - pad, 0)
                x1 = min(int(xs.max()) + pad, image_bgr.shape[1] - 1)
                y1 = min(int(ys.max()) + pad, image_bgr.shape[0] - 1)
                zoom_img = overlay[y0:y1, x0:x1]
                st.image(
                    cv2.cvtColor(zoom_img, cv2.COLOR_BGR2RGB),
                    caption="Orange edge · green fill (matches the movable box)",
                    use_container_width=True,
                )
            except ValueError as exc:
                st.error(str(exc))
                st.session_state.deskewed_raw = None

if ui_mode != "Draw":
    st.info("Lock a view (after zooming/panning) to continue to drawing, transforms, and recognition.")
    st.stop()

st.divider()
st.subheader("Step 2 — Crop & transform (OCR input)")

raw = st.session_state.deskewed_raw
if raw is None:
    st.info("Draw a baseline and set band height to get a deskewed crop here.")
else:
    st.write(
        "Make the street name look **upright and left-to-right** before running OCR. "
        "Transforms apply only to this crop — you do not need to redraw the baseline."
    )

    # Transform controls
    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    with c1:
        if st.button("⟲ 90°", use_container_width=True, help="Rotate 90° counter-clockwise"):
            st.session_state.prep_rot90 = (int(st.session_state.prep_rot90) - 1) % 4
            st.rerun()
    with c2:
        if st.button("⟳ 90°", use_container_width=True, help="Rotate 90° clockwise"):
            st.session_state.prep_rot90 = (int(st.session_state.prep_rot90) + 1) % 4
            st.rerun()
    with c3:
        if st.button("180°", use_container_width=True):
            st.session_state.prep_rot90 = (int(st.session_state.prep_rot90) + 2) % 4
            st.rerun()
    with c4:
        if st.button("Flip H", use_container_width=True):
            st.session_state.prep_flip_h = not bool(st.session_state.prep_flip_h)
            st.rerun()
    with c5:
        if st.button("Flip V", use_container_width=True):
            st.session_state.prep_flip_v = not bool(st.session_state.prep_flip_v)
            st.rerun()
    with c6:
        if st.button("Invert", use_container_width=True):
            st.session_state.prep_invert = not bool(st.session_state.prep_invert)
            st.rerun()
    with c7:
        if st.button("Reset", use_container_width=True, help="Clear all transforms"):
            _reset_transforms()
            st.rerun()

    st.slider(
        "Fine rotate (degrees)",
        min_value=-45.0,
        max_value=45.0,
        step=0.5,
        key="prep_fine_deg",
        help="Small correction after 90° steps. Positive = counter-clockwise (OpenCV convention).",
    )

    transforms = _current_transforms()
    transformed = apply_prep_transforms(raw, transforms)
    # Live preview: show color transform result; OCR will CLAHE+upscale this
    preview_rgb = (
        cv2.cvtColor(transformed, cv2.COLOR_BGR2RGB)
        if transformed.ndim == 3
        else transformed
    )
    st.image(
        preview_rgb,
        caption=f"OCR input preview · {transforms.summary()}",
        use_container_width=True,
    )

    # Let users see what OCR actually receives before spending time running it.
    if handwriting_mode:
        with st.expander("OCR preprocessing variants (handwriting mode)"):
            st.caption(
                "Each Run recognition call tries OCR on all of these and keeps whichever "
                "reading matches each candidate street name best."
            )
            variant_preview = ocr_variants(transformed, target_height=64.0)
            cols = st.columns(len(variant_preview))
            for col, (label, img) in zip(cols, variant_preview):
                with col:
                    st.image(img, caption=label, use_container_width=True)
    else:
        with st.expander("CLAHE + upscale preview (what OCR receives)"):
            prep_preview = preprocess_for_ocr(transformed, upscale=2.0)
            st.session_state.deskewed_prep = prep_preview
            st.image(prep_preview, caption="Preprocessed for OCR", use_container_width=True)

st.divider()
st.subheader("Step 3 — Recognition and top-10 review")

if run_btn:
    if st.session_state.baseline is None or st.session_state.deskewed_raw is None:
        st.error("Draw a baseline and create a crop first.")
    else:
        transforms = _current_transforms()
        transformed = apply_prep_transforms(st.session_state.deskewed_raw, transforms)
        truth = _cached_truth_table()
        names = candidate_names(truth, include_1917=include_1917)
        allowlist = build_allowlist(names) if restrict_charset else None
        ocr_text = ""
        details: list = []
        ocr_readings: list[tuple[str, float, str]] = []

        need_ocr = ranker_mode in ("EasyOCR fuzzy", "Blend both")
        spinner_msg = (
            "Running EasyOCR across preprocessing variants + ranking…"
            if need_ocr and handwriting_mode
            else "Running EasyOCR + ranking…"
            if need_ocr
            else "Running CA cleanup + GA / score-all ranking…"
        )
        with st.spinner(spinner_msg):
            if need_ocr:
                reader = _cached_reader()
                if handwriting_mode:
                    variants = ocr_variants(transformed, target_height=64.0)
                    ocr_readings, details = run_ocr_ensemble(
                        reader,
                        variants,
                        min_conf=min_conf,
                        allowlist=allowlist,
                        decoder="beamsearch",
                    )
                    ocr_text = (
                        max(ocr_readings, key=lambda r: r[1])[0] if ocr_readings else ""
                    )
                    prep = variants[0][1]
                else:
                    prep = preprocess_for_ocr(transformed, upscale=2.0)
                    ocr_text, details = run_ocr(
                        reader, prep, min_conf=min_conf, allowlist=allowlist, decoder="greedy"
                    )
                    ocr_readings = [(ocr_text, 0.0, "clahe+upscale")] if ocr_text else []
                st.session_state.deskewed_prep = prep

            if ranker_mode == "EasyOCR fuzzy":
                if handwriting_mode and len(ocr_readings) > 1:
                    ranked = rank_streets_multi(
                        [t for t, _, _ in ocr_readings], names, truth, top_n=10
                    )
                else:
                    ranked = rank_streets(ocr_text, names, truth, top_n=10)
                st.session_state.ca_binary = None
            else:
                # CA+GA uses transformed crop (before CLAHE) so ink polarity stays natural
                ca_df, ca_bin = rank_ca_ga(
                    transformed,
                    names,
                    truth,
                    ocr_text=ocr_text if ranker_mode == "Blend both" else "",
                    known_chars=known_chars,
                    ca_steps=int(ca_steps),
                    use_ga=not score_all,
                    top_n=40 if ranker_mode == "Blend both" else 10,
                )
                st.session_state.ca_binary = ca_bin
                if ranker_mode == "CA+GA ink":
                    ranked = ca_df.head(10).copy()
                    ranked["rank"] = range(1, len(ranked) + 1)
                else:
                    easy_df = rank_streets(ocr_text, names, truth, top_n=40)
                    # Blend: average normalized scores by street_name
                    scores: dict[str, list[float]] = {}
                    meta_rows: dict[str, dict] = {}
                    for _, row in easy_df.iterrows():
                        name = row["street_name"]
                        scores.setdefault(name, []).append(float(row["match_pct"]) / 100.0)
                        meta_rows[name] = row.to_dict()
                    for _, row in ca_df.iterrows():
                        name = row["street_name"]
                        scores.setdefault(name, []).append(float(row["match_pct"]) / 100.0)
                        meta_rows.setdefault(name, row.to_dict())
                    blended = []
                    for name, vals in scores.items():
                        blended.append((name, sum(vals) / len(vals)))
                    blended.sort(key=lambda x: x[1], reverse=True)
                    rows = []
                    for name, sc in blended[:10]:
                        base = meta_rows.get(name, {})
                        rows.append(
                            {
                                "rank": len(rows) + 1,
                                "street_name": name,
                                "match_pct": round(sc * 100.0, 1),
                                "ocr_text": ocr_text,
                                "year_ranges": base.get("year_ranges", ""),
                                "exists_today": base.get("exists_today", ""),
                                "same_as": base.get("same_as", ""),
                                "method": "blend",
                            }
                        )
                    ranked = pd.DataFrame(rows)

            st.session_state.ocr_text = ocr_text
            st.session_state.ocr_details = details
            st.session_state.ocr_readings = ocr_readings
            st.session_state.top10 = ranked

if st.session_state.top10 is not None:
    st.markdown(f"**Best OCR reading:** `{st.session_state.ocr_text or '(empty)'}`")
    readings = st.session_state.get("ocr_readings") or []
    if len(readings) > 1:
        with st.expander(f"All OCR readings used for ranking ({len(readings)})"):
            st.table(
                pd.DataFrame(
                    [{"text": t, "confidence": round(c, 3), "source": s} for t, c, s in readings]
                )
            )
    if st.session_state.ca_binary is not None:
        with st.expander("CA binary ink preview"):
            preview = (st.session_state.ca_binary * 255).astype("uint8")
            st.image(preview, caption="Ink after cellular-automata cleanup", use_container_width=True)
    if st.session_state.ocr_details:
        with st.expander("Raw EasyOCR boxes"):
            st.json(
                [
                    {"text": d["text"], "confidence": round(d["confidence"], 3)}
                    for d in st.session_state.ocr_details
                ]
            )

    ranked: pd.DataFrame = st.session_state.top10
    if ranked.empty:
        st.warning(
            "No ranked candidates — OCR may have returned empty text. "
            "Try Flip/Rotate so the name reads left-to-right, or adjust band height."
        )
    else:
        st.dataframe(ranked, use_container_width=True, hide_index=True)
        choices = ranked["street_name"].tolist()
        accepted = st.radio(
            "Accept a name (session review only)",
            options=["(none)"] + choices,
            horizontal=False,
        )
        if accepted != "(none)" and st.button("Save acceptance to session log"):
            st.session_state.review_log.append(
                {
                    "image": upload.name,
                    "ocr_text": st.session_state.ocr_text,
                    "accepted": accepted,
                    "transforms": _current_transforms().summary(),
                    "angle_deg": round(st.session_state.baseline.angle_deg, 2)
                    if st.session_state.baseline
                    else None,
                }
            )
            st.success(f"Logged: {accepted}")

if st.session_state.review_log:
    st.subheader("Session review log")
    log_df = pd.DataFrame(st.session_state.review_log)
    st.dataframe(log_df, use_container_width=True, hide_index=True)
    buf = io.StringIO()
    log_df.to_csv(buf, index=False)
    st.download_button(
        "Download review log CSV",
        buf.getvalue(),
        file_name="street_ocr_review_log.csv",
    )
