"""Baseline → text band polygon and deskew-to-horizontal crop."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class Baseline:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def length(self) -> float:
        return float(np.hypot(self.x2 - self.x1, self.y2 - self.y1))

    @property
    def angle_deg(self) -> float:
        return float(np.degrees(np.arctan2(self.y2 - self.y1, self.x2 - self.x1)))


@dataclass
class DeskewResult:
    image: np.ndarray  # BGR or gray uint8, horizontal
    angle_deg: float
    length_px: float
    height_px: float
    corners: np.ndarray  # 4x2 float in source image coords (p1,p2,p3,p4)


def _unit(vx: float, vy: float) -> tuple[float, float]:
    n = float(np.hypot(vx, vy))
    if n < 1e-6:
        return 1.0, 0.0
    return vx / n, vy / n


def full_to_canvas(
    x: float,
    y: float,
    *,
    scale: float,
    origin_xy: tuple[float, float],
) -> tuple[float, float]:
    ox, oy = origin_xy
    return (x - ox) * scale, (y - oy) * scale


def canvas_to_full(
    x: float,
    y: float,
    *,
    scale: float,
    origin_xy: tuple[float, float],
) -> tuple[float, float]:
    ox, oy = origin_xy
    inv = 1.0 / scale if scale else 1.0
    return ox + x * inv, oy + y * inv


def band_corners(
    baseline: Baseline,
    height: float,
    text_above: bool = True,
) -> np.ndarray:
    """Return 4 corners (p1, p2, p3, p4) in image coordinates.

    p1--p2 is the baseline; p4--p3 is the far edge through the text.
    """
    dx, dy = _unit(baseline.x2 - baseline.x1, baseline.y2 - baseline.y1)
    # Perpendicular: rotate direction 90° CCW; flip if text is below baseline
    nx, ny = -dy, dx
    if not text_above:
        nx, ny = -nx, -ny

    p1 = np.array([baseline.x1, baseline.y1], dtype=np.float32)
    p2 = np.array([baseline.x2, baseline.y2], dtype=np.float32)
    offset = np.array([nx, ny], dtype=np.float32) * float(height)
    p4 = p1 + offset
    p3 = p2 + offset
    return np.stack([p1, p2, p3, p4], axis=0)


def deskew_band(
    image: np.ndarray,
    baseline: Baseline,
    height: float,
    text_above: bool = True,
    pad: int = 4,
) -> DeskewResult:
    """Perspective-warp the extruded band to a horizontal rectangle."""
    if height < 2:
        raise ValueError("Band height must be at least 2 pixels")
    length = baseline.length
    if length < 2:
        raise ValueError("Baseline is too short")

    corners = band_corners(baseline, height, text_above=text_above)
    out_w = max(int(round(length)) + 2 * pad, 8)
    out_h = max(int(round(height)) + 2 * pad, 8)

    # Destination: horizontal strip (baseline along bottom if text_above)
    dst = np.array(
        [
            [pad, out_h - 1 - pad],  # p1
            [out_w - 1 - pad, out_h - 1 - pad],  # p2
            [out_w - 1 - pad, pad],  # p3
            [pad, pad],  # p4
        ],
        dtype=np.float32,
    )
    if not text_above:
        # Text was below baseline; flip so text still reads upright-ish
        dst = np.array(
            [
                [pad, pad],
                [out_w - 1 - pad, pad],
                [out_w - 1 - pad, out_h - 1 - pad],
                [pad, out_h - 1 - pad],
            ],
            dtype=np.float32,
        )

    matrix = cv2.getPerspectiveTransform(corners.astype(np.float32), dst)
    warped = cv2.warpPerspective(
        image,
        matrix,
        (out_w, out_h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )
    return DeskewResult(
        image=warped,
        angle_deg=baseline.angle_deg,
        length_px=length,
        height_px=float(height),
        corners=corners,
    )


def preprocess_for_ocr(
    bgr_or_gray: np.ndarray,
    upscale: float = 2.0,
    *,
    target_height: float | None = None,
    denoise: bool = False,
    sharpen: bool = True,
    clip_limit: float = 2.0,
) -> np.ndarray:
    """Grayscale + (optional denoise) + CLAHE + (optional sharpen) + upscale.

    ``target_height``, if given, overrides ``upscale`` with whatever factor
    is needed to bring the crop's height up to that many pixels. Handwritten
    street labels are often only 15-25px tall after deskewing; EasyOCR (and
    OCR generally) needs letters closer to 40-60px tall to have a real
    chance, so undersized crops are the single biggest reason recognition
    fails on this kind of source material.
    """
    if bgr_or_gray.ndim == 3:
        gray = cv2.cvtColor(bgr_or_gray, cv2.COLOR_BGR2GRAY)
    else:
        gray = bgr_or_gray

    if target_height:
        h = max(int(gray.shape[0]), 1)
        upscale = max(float(upscale), float(target_height) / float(h))
        upscale = min(upscale, 8.0)  # guard against absurd blow-ups on tiny bands

    if denoise:
        gray = cv2.fastNlMeansDenoising(gray, h=7, templateWindowSize=7, searchWindowSize=21)

    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    if upscale and upscale != 1.0:
        enhanced = cv2.resize(
            enhanced,
            None,
            fx=upscale,
            fy=upscale,
            interpolation=cv2.INTER_CUBIC,
        )

    if sharpen:
        # Mild unsharp mask: helps faint pencil/pen strokes read as continuous
        # ink instead of dotted fragments after upscaling.
        blur = cv2.GaussianBlur(enhanced, (0, 0), sigmaX=1.2)
        enhanced = cv2.addWeighted(enhanced, 1.6, blur, -0.6, 0)

    return enhanced


def adaptive_binarize(gray: np.ndarray, block_size: int = 31, c: int = 10) -> np.ndarray:
    """Local adaptive threshold — locks onto faint/uneven ink that a single
    global threshold (or CLAHE alone) washes out, which is common on scanned
    old maps with stained or unevenly lit paper."""
    block_size = int(block_size)
    if block_size % 2 == 0:
        block_size += 1
    block_size = max(block_size, 3)
    return cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        block_size,
        c,
    )


def ocr_variants(
    transformed: np.ndarray,
    *,
    target_height: float = 64.0,
) -> list[tuple[str, np.ndarray]]:
    """Build a small ensemble of OCR-ready renderings of the same crop.

    No single fixed pipeline (grayscale+CLAHE+upscale) is right for every
    scan: faint pencil needs denoise+sharpen, stained paper needs adaptive
    thresholding, and some crops OCR better inverted. Rather than guess one
    combination, produce a few and let the caller run OCR on all of them and
    keep whichever reading each candidate street name matches best.
    """
    gray = (
        cv2.cvtColor(transformed, cv2.COLOR_BGR2GRAY) if transformed.ndim == 3 else transformed
    )

    variants: list[tuple[str, np.ndarray]] = [
        (
            "clahe+sharpen",
            preprocess_for_ocr(gray, target_height=target_height, denoise=False, sharpen=True),
        ),
        (
            "denoise+clahe+sharpen",
            preprocess_for_ocr(gray, target_height=target_height, denoise=True, sharpen=True),
        ),
        (
            "inverted",
            preprocess_for_ocr(
                cv2.bitwise_not(gray), target_height=target_height, denoise=False, sharpen=True
            ),
        ),
    ]

    h = max(int(gray.shape[0]), 1)
    up_scale = max(1.0, min(target_height / h, 8.0))
    up = cv2.resize(gray, None, fx=up_scale, fy=up_scale, interpolation=cv2.INTER_CUBIC)
    variants.append(("adaptive-threshold", adaptive_binarize(up)))

    return variants


@dataclass
class PrepTransforms:
    """User transforms applied to the deskewed crop before OCR."""

    rot90: int = 0  # quarter-turns CW, 0..3
    fine_deg: float = 0.0
    flip_h: bool = False
    flip_v: bool = False
    invert: bool = False

    def summary(self) -> str:
        parts = [f"rot90={self.rot90 % 4}"]
        if abs(self.fine_deg) > 1e-6:
            parts.append(f"fine={self.fine_deg:+.1f}°")
        if self.flip_h:
            parts.append("flipH")
        if self.flip_v:
            parts.append("flipV")
        if self.invert:
            parts.append("invert")
        return " · ".join(parts)


def rotate_exact(img: np.ndarray, k: int) -> np.ndarray:
    """Rotate by k*90° clockwise (k mod 4)."""
    k = int(k) % 4
    if k == 0:
        return img
    if k == 1:
        return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    if k == 2:
        return cv2.rotate(img, cv2.ROTATE_180)
    return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)


def rotate_fine(img: np.ndarray, degrees: float) -> np.ndarray:
    """Rotate about center; expand canvas so corners are not clipped."""
    if abs(degrees) < 1e-6:
        return img
    h, w = img.shape[:2]
    center = (w / 2.0, h / 2.0)
    matrix = cv2.getRotationMatrix2D(center, degrees, 1.0)
    cos = abs(matrix[0, 0])
    sin = abs(matrix[0, 1])
    new_w = int(np.ceil(h * sin + w * cos))
    new_h = int(np.ceil(h * cos + w * sin))
    matrix[0, 2] += (new_w / 2.0) - center[0]
    matrix[1, 2] += (new_h / 2.0) - center[1]
    border = (240, 240, 240) if img.ndim == 3 else 240
    return cv2.warpAffine(
        img,
        matrix,
        (new_w, new_h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=border,
    )


def apply_prep_transforms(img: np.ndarray, transforms: PrepTransforms) -> np.ndarray:
    """Compose: rot90 → fine rotate → flips → invert."""
    out = img
    out = rotate_exact(out, transforms.rot90)
    out = rotate_fine(out, transforms.fine_deg)
    if transforms.flip_h:
        out = cv2.flip(out, 1)
    if transforms.flip_v:
        out = cv2.flip(out, 0)
    if transforms.invert:
        out = cv2.bitwise_not(out)
    return out


def overlay_band(
    image: np.ndarray,
    corners: np.ndarray,
    color: tuple[int, int, int] = (0, 220, 0),
    thickness: int = 2,
) -> np.ndarray:
    """Draw the band polygon on a copy of the image (BGR)."""
    out = image.copy()
    if out.ndim == 2:
        out = cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)
    pts = corners.astype(np.int32).reshape((-1, 1, 2))
    cv2.polylines(out, [pts], isClosed=True, color=color, thickness=thickness)
    # baseline thicker
    p1, p2 = corners[0].astype(int), corners[1].astype(int)
    cv2.line(out, tuple(p1), tuple(p2), (0, 140, 255), thickness + 1)
    return out


@dataclass
class Viewport:
    """Crop of the full image shown on the drawing canvas."""

    x: float
    y: float
    w: float
    h: float
    disp_w: int
    disp_h: int

    @property
    def scale(self) -> float:
        """canvas_px / full_res_px within the viewport."""
        return float(self.disp_w) / float(self.w) if self.w else 1.0


def viewport_from_pixel_bounds(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    img_w: int,
    img_h: int,
    max_w: int = 1100,
    max_h: int = 900,
) -> Viewport:
    """Build a Viewport from an axis-aligned full-res pixel rectangle."""
    xa = float(np.clip(min(x0, x1), 0, img_w))
    xb = float(np.clip(max(x0, x1), 0, img_w))
    ya = float(np.clip(min(y0, y1), 0, img_h))
    yb = float(np.clip(max(y0, y1), 0, img_h))
    vw = max(xb - xa, 1.0)
    vh = max(yb - ya, 1.0)
    scale = min(max_w / vw, max_h / vh)
    disp_w = max(1, int(round(vw * scale)))
    disp_h = max(1, int(round(vh * scale)))
    return Viewport(xa, ya, vw, vh, disp_w, disp_h)


def compute_viewport(
    img_w: int,
    img_h: int,
    zoom: float,
    pan_x: float,
    pan_y: float,
    max_w: int = 1100,
    max_h: int = 900,
) -> Viewport:
    """Viewport in full-res pixels + display size.

    zoom=1 shows the whole image fitted to max_w/max_h.
    zoom>1 shows a centered-panable crop, upscaled to the display budget.
    pan_x/pan_y in [0, 1] select the crop origin when zoomed.
    """
    zoom = max(float(zoom), 1.0)
    pan_x = min(max(float(pan_x), 0.0), 1.0)
    pan_y = min(max(float(pan_y), 0.0), 1.0)

    vw = img_w / zoom
    vh = img_h / zoom
    vx = pan_x * max(img_w - vw, 0.0)
    vy = pan_y * max(img_h - vh, 0.0)

    # Fit crop into display budget (prefer width, then clamp height)
    if zoom <= 1.0 + 1e-6:
        scale = min(1.0, max_w / float(img_w), max_h / float(img_h))
        disp_w = max(1, int(round(img_w * scale)))
        disp_h = max(1, int(round(img_h * scale)))
        return Viewport(0.0, 0.0, float(img_w), float(img_h), disp_w, disp_h)

    scale = min(max_w / vw, max_h / vh)
    disp_w = max(1, int(round(vw * scale)))
    disp_h = max(1, int(round(vh * scale)))
    return Viewport(vx, vy, vw, vh, disp_w, disp_h)


def make_viewport_image(image_bgr: np.ndarray, viewport: Viewport) -> "Image":
    """Crop + resize the viewport for use as a canvas background (RGB PIL)."""
    from PIL import Image

    h, w = image_bgr.shape[:2]
    x0 = int(np.floor(viewport.x))
    y0 = int(np.floor(viewport.y))
    x1 = min(w, int(np.ceil(viewport.x + viewport.w)))
    y1 = min(h, int(np.ceil(viewport.y + viewport.h)))
    x0 = max(0, x0)
    y0 = max(0, y0)
    crop = image_bgr[y0:y1, x0:x1]
    if crop.size == 0:
        crop = image_bgr
    rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(rgb).resize(
        (viewport.disp_w, viewport.disp_h),
        Image.Resampling.LANCZOS,
    )
    return pil


def band_to_fabric_rect(
    baseline: Baseline,
    height: float,
    *,
    scale: float,
    origin_xy: tuple[float, float],
    text_above: bool = True,
) -> dict:
    """Build a Fabric.js rect JSON for the band (canvas coordinates, center origin)."""
    corners = band_corners(baseline, height, text_above=text_above)
    # Canvas-space corners
    pts = [full_to_canvas(float(p[0]), float(p[1]), scale=scale, origin_xy=origin_xy) for p in corners]
    # Center of quadrilateral
    cx = sum(p[0] for p in pts) / 4.0
    cy = sum(p[1] for p in pts) / 4.0
    length = baseline.length * scale
    height_c = float(height) * scale
    angle = baseline.angle_deg  # fabric angle is CW degrees from +x; baseline atan2 matches
    # Fill green-ish, stroke orange to match overlay legend
    return {
        "type": "rect",
        "version": "4.4.0",
        "originX": "center",
        "originY": "center",
        "left": cx,
        "top": cy,
        "width": max(length, 2.0),
        "height": max(height_c, 2.0),
        "fill": "rgba(0, 220, 0, 0.25)",
        "stroke": "#ff8c00",
        "strokeWidth": 2,
        "angle": angle,
        "scaleX": 1,
        "scaleY": 1,
        "selectable": True,
        "name": "street_band",
    }


def fabric_rect_to_baseline(
    obj: dict,
    *,
    scale: float,
    origin_xy: tuple[float, float],
    text_above: bool = True,
) -> tuple[Baseline, float] | None:
    """Recover full-res Baseline + band height from a transformed Fabric rect."""
    if not obj or obj.get("type") != "rect":
        return None
    w = float(obj.get("width", 0)) * float(obj.get("scaleX", 1) or 1)
    h = float(obj.get("height", 0)) * float(obj.get("scaleY", 1) or 1)
    if w < 2 or h < 2:
        return None
    angle = float(obj.get("angle", 0) or 0)
    # left/top are the origin point in canvas coords
    left = float(obj.get("left", 0))
    top = float(obj.get("top", 0))
    origin_x = obj.get("originX", "left")
    origin_y = obj.get("originY", "top")
    # Convert left/top to center
    cx, cy = left, top
    if origin_x == "left":
        cx = left + w / 2.0
    elif origin_x == "right":
        cx = left - w / 2.0
    if origin_y == "top":
        cy = top + h / 2.0
    elif origin_y == "bottom":
        cy = top - h / 2.0

    rad = np.radians(angle)
    cos_a, sin_a = np.cos(rad), np.sin(rad)
    # Unrotated corners relative to center: baseline is bottom edge if text_above
    # Local coords: x along width, y along height (down positive in fabric)
    # With Y-down + Fabric CW angle = baseline atan2, local +y points toward
    # the text side when text_above=True. Baseline is the opposite edge.
    if text_above:
        local = [
            (-w / 2.0, -h / 2.0),  # p1
            (w / 2.0, -h / 2.0),  # p2
        ]
    else:
        local = [
            (-w / 2.0, h / 2.0),
            (w / 2.0, h / 2.0),
        ]

    def rot(lx: float, ly: float) -> tuple[float, float]:
        return cx + lx * cos_a - ly * sin_a, cy + lx * sin_a + ly * cos_a

    c1 = rot(*local[0])
    c2 = rot(*local[1])
    f1 = canvas_to_full(c1[0], c1[1], scale=scale, origin_xy=origin_xy)
    f2 = canvas_to_full(c2[0], c2[1], scale=scale, origin_xy=origin_xy)
    height_full = h / scale if scale else h
    return Baseline(f1[0], f1[1], f2[0], f2[1]), float(height_full)


def translate_baseline(baseline: Baseline, dx: float, dy: float) -> Baseline:
    return Baseline(
        baseline.x1 + dx,
        baseline.y1 + dy,
        baseline.x2 + dx,
        baseline.y2 + dy,
    )


def canvas_stroke_to_baseline(
    stroke_objects: list,
    scale: float,
    origin_xy: tuple[float, float] = (0.0, 0.0),
) -> Baseline | None:
    """Extract a Baseline from streamlit-drawable-canvas JSON objects.

    ``scale`` is canvas_px / full_res_px inside the current viewport
    (``disp_w / vw``). ``origin_xy`` is the viewport top-left in full-res
    image coordinates.
    """
    if not stroke_objects:
        return None
    ox, oy = origin_xy
    # Prefer the last line/path stroke
    for obj in reversed(stroke_objects):
        obj_type = obj.get("type")
        if obj_type == "line":
            # fabric.js line: x1,y1,x2,y2 relative to left/top
            left = float(obj.get("left", 0))
            top = float(obj.get("top", 0))
            x1 = left + float(obj.get("x1", 0))
            y1 = top + float(obj.get("y1", 0))
            x2 = left + float(obj.get("x2", 0))
            y2 = top + float(obj.get("y2", 0))
        elif obj_type == "path":
            path = obj.get("path") or []
            points: list[tuple[float, float]] = []
            for cmd in path:
                if not cmd:
                    continue
                # ['M', x, y] or ['L', x, y] or ['Q', ...]
                if cmd[0] in ("M", "L") and len(cmd) >= 3:
                    points.append((float(cmd[1]), float(cmd[2])))
                elif cmd[0] == "Q" and len(cmd) >= 5:
                    points.append((float(cmd[3]), float(cmd[4])))
            if len(points) < 2:
                continue
            x1, y1 = points[0]
            x2, y2 = points[-1]
        else:
            continue

        inv = 1.0 / scale if scale else 1.0
        return Baseline(
            ox + x1 * inv,
            oy + y1 * inv,
            ox + x2 * inv,
            oy + y2 * inv,
        )
    return None
