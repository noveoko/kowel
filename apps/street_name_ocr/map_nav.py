"""Leaflet (Folium) navigator for map images: wheel zoom + middle-button pan."""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path

import cv2
import folium
import numpy as np
from branca.element import Element, MacroElement
from jinja2 import Template

from geometry import Viewport, viewport_from_pixel_bounds

CACHE_DIR = Path(__file__).resolve().parent / ".cache"


class MiddleMousePan(MacroElement):
    """Enable pan while the middle mouse button is held; block autoscroll."""

    _template = Template(
        """
        {% macro script(this, kwargs) %}
        (function() {
            var map = {{ this._parent.get_name() }};
            var dragging = false;
            var last = null;

            function onDown(e) {
                var oe = e.originalEvent || e;
                if (oe.button !== 1) return;
                oe.preventDefault();
                dragging = true;
                last = {x: oe.clientX, y: oe.clientY};
                map.dragging.disable();
            }
            function onMove(e) {
                if (!dragging || !last) return;
                var oe = e.originalEvent || e;
                oe.preventDefault();
                var dx = oe.clientX - last.x;
                var dy = oe.clientY - last.y;
                last = {x: oe.clientX, y: oe.clientY};
                map.panBy([-dx, -dy], {animate: false});
            }
            function onUp(e) {
                if (!dragging) return;
                dragging = false;
                last = null;
                map.dragging.enable();
            }
            map.on('mousedown', onDown);
            map.on('mousemove', onMove);
            map.on('mouseup', onUp);
            map.on('mouseout', onUp);
            var el = map.getContainer();
            el.addEventListener('auxclick', function(ev) { ev.preventDefault(); });
            el.addEventListener('mousedown', function(ev) {
                if (ev.button === 1) ev.preventDefault();
            });
        })();
        {% endmacro %}
        """
    )


def _ensure_cache() -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR


def nav_image_path(image_bgr: np.ndarray, max_edge: int = 2000) -> tuple[Path, float]:
    """Save a (possibly downsampled) PNG for Folium; return path and scale vs full-res.

    ``full_to_nav = nav_px / full_px`` (uniform). Bounds from Leaflet are in nav pixels
    when using ImageOverlay sized to the saved image; convert back with / scale.
    """
    h, w = image_bgr.shape[:2]
    scale = 1.0
    out = image_bgr
    longest = max(h, w)
    if longest > max_edge:
        scale = max_edge / float(longest)
        out = cv2.resize(
            image_bgr,
            (max(1, int(round(w * scale))), max(1, int(round(h * scale)))),
            interpolation=cv2.INTER_AREA,
        )
    digest = hashlib.md5(out.tobytes()).hexdigest()[:16]
    path = _ensure_cache() / f"nav_{digest}_{out.shape[1]}x{out.shape[0]}.png"
    if not path.exists():
        cv2.imwrite(str(path), out)
    return path, scale


def image_to_data_uri(path: Path) -> str:
    data = path.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:image/png;base64,{b64}"


def build_image_map(
    image_bgr: np.ndarray,
    width: int = 900,
    height: int = 650,
    center: list[float] | None = None,
    zoom: float | None = None,
) -> tuple[folium.Map, float, int, int]:
    """Return (map, nav_scale, nav_w, nav_h).

    CRS.Simple with bounds [[-nav_h, 0], [0, nav_w]] so +x right, +y down in pixel space
    maps to lng=x, lat=-y.

    Pass ``center`` / ``zoom`` from a previous ``st_folium`` return value so Streamlit
    reruns do not reset the user's view.
    """
    path, nav_scale = nav_image_path(image_bgr)
    nav = cv2.imread(str(path), cv2.IMREAD_COLOR)
    nav_h, nav_w = nav.shape[:2]
    uri = image_to_data_uri(path)

    loc = center if center is not None else [-nav_h / 2, nav_w / 2]
    # CRS.Simple zoom: 0 often fits; keep prior zoom when provided
    z0 = 0 if zoom is None else float(zoom)

    m = folium.Map(
        location=loc,
        zoom_start=z0,
        crs="Simple",
        tiles=None,
        prefer_canvas=True,
        width=width,
        height=height,
    )
    folium.raster_layers.ImageOverlay(
        image=uri,
        bounds=[[-nav_h, 0], [0, nav_w]],
        opacity=1,
        interactive=False,
        cross_origin=False,
        zindex=1,
    ).add_to(m)
    if zoom is None and center is None:
        m.fit_bounds([[-nav_h, 0], [0, nav_w]])
    MiddleMousePan().add_to(m)

    m.get_root().html.add_child(
        Element("<style>.leaflet-control-attribution{display:none!important}</style>")
    )
    return m, nav_scale, nav_w, nav_h


def leaflet_bounds_to_full_pixels(
    bounds: dict,
    *,
    nav_scale: float,
    img_w: int,
    img_h: int,
) -> tuple[float, float, float, float] | None:
    """Convert st_folium bounds dict to full-res pixel (x0,y0,x1,y1)."""
    if not bounds:
        return None
    try:
        sw = bounds.get("_southWest") or bounds.get("southWest") or bounds["south_west"]
        ne = bounds.get("_northEast") or bounds.get("northEast") or bounds["north_east"]
        # Folium sometimes returns {lat,lng} nested differently
        if "lat" in sw:
            south, west = float(sw["lat"]), float(sw["lng"])
            north, east = float(ne["lat"]), float(ne["lng"])
        else:
            return None
    except (KeyError, TypeError, ValueError):
        return None

    # lat = -y_nav, lng = x_nav
    x0_nav = west
    x1_nav = east
    y0_nav = -north
    y1_nav = -south

    inv = 1.0 / nav_scale if nav_scale else 1.0
    x0 = x0_nav * inv
    x1 = x1_nav * inv
    y0 = y0_nav * inv
    y1 = y1_nav * inv
    return (x0, y0, x1, y1)


def bounds_to_viewport(
    bounds: dict | None,
    *,
    nav_scale: float,
    img_w: int,
    img_h: int,
    max_w: int = 1100,
    max_h: int = 900,
) -> Viewport | None:
    px = leaflet_bounds_to_full_pixels(
        bounds or {},
        nav_scale=nav_scale,
        img_w=img_w,
        img_h=img_h,
    )
    if px is None:
        return None
    x0, y0, x1, y1 = px
    return viewport_from_pixel_bounds(x0, y0, x1, y1, img_w, img_h, max_w=max_w, max_h=max_h)


def full_image_viewport(img_w: int, img_h: int, max_w: int = 1100, max_h: int = 900) -> Viewport:
    return viewport_from_pixel_bounds(0, 0, img_w, img_h, img_w, img_h, max_w=max_w, max_h=max_h)
