"""CA ink cleanup + GA / score-all ranking against the street truth table.

Designed for degraded map labels: cellular automata cleans binary ink;
a genetic algorithm (or exhaustive score-all) searches the closed candidate
set using 1D projection fitness, length priors, optional OCR and known chars.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

import cv2
import numpy as np
import pandas as pd
from rapidfuzz import fuzz

# Relative character width weights for synthetic 1D profiles (map-font-ish).
_CHAR_WIDTH = {
    "i": 0.45,
    "j": 0.5,
    "l": 0.45,
    "t": 0.55,
    "f": 0.55,
    "r": 0.6,
    "c": 0.7,
    "s": 0.7,
    "z": 0.7,
    "e": 0.75,
    "a": 0.8,
    "o": 0.85,
    "n": 0.85,
    "u": 0.85,
    "h": 0.85,
    "k": 0.85,
    "b": 0.85,
    "d": 0.85,
    "p": 0.85,
    "g": 0.9,
    "q": 0.9,
    "y": 0.85,
    "v": 0.8,
    "x": 0.8,
    "m": 1.25,
    "w": 1.3,
    "ł": 0.5,
    "ń": 0.85,
    "ś": 0.7,
    "ć": 0.7,
    "ź": 0.7,
    "ż": 0.75,
    "ó": 0.85,
    "ą": 0.85,
    "ę": 0.8,
    " ": 0.35,
    "-": 0.4,
    ".": 0.35,
}


def _fold(s: str) -> str:
    s = (s or "").strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s


def binarize_ink(gray_or_bgr: np.ndarray, force_invert: bool | None = None) -> np.ndarray:
    """Return uint8 binary image with ink=1, background=0."""
    if gray_or_bgr.ndim == 3:
        gray = cv2.cvtColor(gray_or_bgr, cv2.COLOR_BGR2GRAY)
    else:
        gray = gray_or_bgr
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    _, bw = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # Decide polarity: ink usually darker → fewer ink pixels if we take dark as ink
    dark_as_ink = (bw == 0).astype(np.uint8)
    light_as_ink = (bw == 255).astype(np.uint8)
    if force_invert is True:
        ink = light_as_ink
    elif force_invert is False:
        ink = dark_as_ink
    else:
        # Prefer the polarity with a moderate ink fraction (labels are sparse)
        def score(arr: np.ndarray) -> float:
            frac = float(arr.mean())
            return -abs(frac - 0.18)

        ink = dark_as_ink if score(dark_as_ink) >= score(light_as_ink) else light_as_ink
    return ink


def ca_cleanup(binary: np.ndarray, steps: int = 3) -> np.ndarray:
    """Totalistic CA: kill isolated ink, birth into dense neighborhoods."""
    grid = (binary > 0).astype(np.uint8)
    if steps <= 0:
        return grid
    kernel = np.array([[1, 1, 1], [1, 0, 1], [1, 1, 1]], dtype=np.uint8)
    for _ in range(int(steps)):
        neighbors = cv2.filter2D(grid, -1, kernel, borderType=cv2.BORDER_REPLICATE)
        die = (grid == 1) & (neighbors < 2)
        birth = (grid == 0) & (neighbors >= 5)
        grid = grid.copy()
        grid[die] = 0
        grid[birth] = 1
    return grid


def ink_bbox_width(binary: np.ndarray) -> float:
    ys, xs = np.where(binary > 0)
    if len(xs) == 0:
        return 0.0
    return float(xs.max() - xs.min() + 1)


def horizontal_projection(binary: np.ndarray, length: int = 128) -> np.ndarray:
    """Column ink sums over the ink bbox, resampled to ``length``, L2-normalized."""
    ys, xs = np.where(binary > 0)
    if len(xs) == 0:
        return np.zeros(length, dtype=np.float64)
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    crop = binary[y0:y1, x0:x1]
    proj = crop.sum(axis=0).astype(np.float64)
    if proj.size < 2:
        out = np.zeros(length, dtype=np.float64)
        out[0] = 1.0
        return out
    # resample
    xp = np.linspace(0, 1, num=proj.size)
    xq = np.linspace(0, 1, num=length)
    resampled = np.interp(xq, xp, proj)
    n = np.linalg.norm(resampled)
    if n < 1e-9:
        return np.zeros(length, dtype=np.float64)
    return resampled / n


def _char_w(ch: str) -> float:
    cl = ch.lower()
    if cl in _CHAR_WIDTH:
        return _CHAR_WIDTH[cl]
    folded = _fold(ch)
    if folded and folded[0] in _CHAR_WIDTH:
        return _CHAR_WIDTH[folded[0]]
    return 0.8


def synthetic_projection(name: str, length: int = 128) -> np.ndarray:
    """Build a crude 1D ink profile from character width weights."""
    if not name:
        return np.zeros(length, dtype=np.float64)
    weights = [_char_w(ch) for ch in name]
    total = sum(weights) or 1.0
    profile = np.zeros(length, dtype=np.float64)
    cursor = 0.0
    for w in weights:
        frag = w / total
        a = int(round(cursor * length))
        b = int(round((cursor + frag) * length))
        b = max(b, a + 1)
        b = min(b, length)
        # hump per glyph
        for i in range(a, b):
            t = (i - a + 0.5) / max(b - a, 1)
            profile[i] += 0.35 + 0.65 * np.sin(np.pi * min(max(t, 0.0), 1.0))
        cursor += frag
    n = np.linalg.norm(profile)
    if n < 1e-9:
        return profile
    return profile / n


def warp_projection(profile: np.ndarray, scale: float, x_shift: float) -> np.ndarray:
    """Scale and shift a 1D profile (pad/crop), re-normalize."""
    n = profile.size
    scale = float(np.clip(scale, 0.7, 1.3))
    new_len = max(8, int(round(n * scale)))
    xp = np.linspace(0, 1, num=n)
    xq = np.linspace(0, 1, num=new_len)
    scaled = np.interp(xq, xp, profile)
    # place into buffer of size n with fractional shift
    out = np.zeros(n, dtype=np.float64)
    shift_px = int(round(x_shift * n))
    src_a = max(0, -shift_px)
    dst_a = max(0, shift_px)
    length = min(new_len - src_a, n - dst_a)
    if length > 0:
        # resample scaled into contact region
        piece = scaled[src_a : src_a + length]
        if piece.size != length:
            piece = np.interp(
                np.linspace(0, 1, length),
                np.linspace(0, 1, max(piece.size, 1)),
                piece if piece.size else np.zeros(1),
            )
        out[dst_a : dst_a + length] = piece[:length]
    norm = np.linalg.norm(out)
    if norm < 1e-9:
        return out
    return out / norm


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def length_score(name: str, ink_width: float, px_per_char: float = 14.0) -> float:
    if ink_width <= 1 or not name:
        return 0.0
    expected = max(len(name), 1) * px_per_char
    ratio = ink_width / expected
    # peak at 1.0; half-score at ~0.5x or 2x
    return float(np.exp(-0.5 * ((ratio - 1.0) / 0.35) ** 2))


def known_char_score(name: str, known: str) -> float:
    chars = [c for c in _fold(known) if c.isalnum()]
    if not chars:
        return 0.5  # neutral
    folded = _fold(name)
    hits = sum(1 for c in chars if c in folded)
    return hits / len(chars)


def ocr_score(name: str, ocr_text: str) -> float:
    if not ocr_text or not ocr_text.strip():
        return 0.0
    return float(fuzz.WRatio(_fold(ocr_text), _fold(name))) / 100.0


@dataclass
class FitnessWeights:
    projection: float = 0.45
    length: float = 0.25
    ocr: float = 0.20
    known: float = 0.10


def fitness(
    name: str,
    observed_proj: np.ndarray,
    ink_width: float,
    ocr_text: str = "",
    known_chars: str = "",
    scale: float = 1.0,
    x_shift: float = 0.0,
    weights: FitnessWeights | None = None,
    px_per_char: float = 14.0,
) -> float:
    w = weights or FitnessWeights()
    # renormalize if OCR empty → push weight to projection/length
    wp, wl, wo, wk = w.projection, w.length, w.ocr, w.known
    if not (ocr_text or "").strip():
        wp += wo * 0.6
        wl += wo * 0.4
        wo = 0.0
    if not known_chars.strip():
        wp += wk * 0.5
        wl += wk * 0.5
        wk = 0.0
    total_w = wp + wl + wo + wk or 1.0
    synth = synthetic_projection(name, length=observed_proj.size)
    synth = warp_projection(synth, scale, x_shift)
    s_proj = cosine(observed_proj, synth)
    s_len = length_score(name, ink_width, px_per_char=px_per_char)
    s_ocr = ocr_score(name, ocr_text)
    s_known = known_char_score(name, known_chars)
    return (wp * s_proj + wl * s_len + wo * s_ocr + wk * s_known) / total_w


@dataclass
class Individual:
    name_idx: int
    scale: float = 1.0
    x_shift: float = 0.0
    score: float = 0.0


def _tournament(pop: list[Individual], k: int = 3, rng: np.random.Generator | None = None) -> Individual:
    rng = rng or np.random.default_rng()
    picks = [pop[i] for i in rng.choice(len(pop), size=min(k, len(pop)), replace=False)]
    return max(picks, key=lambda ind: ind.score)


def run_ga(
    candidates: list[str],
    observed_proj: np.ndarray,
    ink_width: float,
    ocr_text: str = "",
    known_chars: str = "",
    pop_size: int = 40,
    generations: int = 25,
    elite: int = 4,
    mutation_rate: float = 0.15,
    seed: int = 42,
) -> list[Individual]:
    """Evolve name index + scale/shift; return final population sorted by score."""
    rng = np.random.default_rng(seed)
    n = len(candidates)
    if n == 0:
        return []

    def eval_ind(ind: Individual) -> Individual:
        ind.score = fitness(
            candidates[ind.name_idx],
            observed_proj,
            ink_width,
            ocr_text=ocr_text,
            known_chars=known_chars,
            scale=ind.scale,
            x_shift=ind.x_shift,
        )
        return ind

    pop = [
        eval_ind(
            Individual(
                name_idx=int(rng.integers(0, n)),
                scale=float(rng.uniform(0.85, 1.15)),
                x_shift=float(rng.uniform(-0.1, 0.1)),
            )
        )
        for _ in range(pop_size)
    ]

    for _ in range(generations):
        pop.sort(key=lambda ind: ind.score, reverse=True)
        next_pop = [Individual(p.name_idx, p.scale, p.x_shift, p.score) for p in pop[:elite]]
        while len(next_pop) < pop_size:
            a, b = _tournament(pop, rng=rng), _tournament(pop, rng=rng)
            child = Individual(
                name_idx=a.name_idx if rng.random() < 0.5 else b.name_idx,
                scale=0.5 * (a.scale + b.scale),
                x_shift=0.5 * (a.x_shift + b.x_shift),
            )
            if rng.random() < mutation_rate:
                child.name_idx = int(rng.integers(0, n))
            if rng.random() < mutation_rate:
                child.scale = float(np.clip(child.scale + rng.normal(0, 0.08), 0.75, 1.25))
            if rng.random() < mutation_rate:
                child.x_shift = float(np.clip(child.x_shift + rng.normal(0, 0.05), -0.15, 0.15))
            next_pop.append(eval_ind(child))
        pop = next_pop

    pop.sort(key=lambda ind: ind.score, reverse=True)
    return pop


def score_all(
    candidates: list[str],
    observed_proj: np.ndarray,
    ink_width: float,
    ocr_text: str = "",
    known_chars: str = "",
) -> list[tuple[str, float]]:
    scored = [
        (
            name,
            fitness(
                name,
                observed_proj,
                ink_width,
                ocr_text=ocr_text,
                known_chars=known_chars,
            ),
        )
        for name in candidates
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def prepare_ink(
    image: np.ndarray,
    ca_steps: int = 3,
    force_invert: bool | None = None,
) -> tuple[np.ndarray, np.ndarray, float]:
    """Return (binary_after_ca, projection, ink_width)."""
    binary0 = binarize_ink(image, force_invert=force_invert)
    binary = ca_cleanup(binary0, steps=ca_steps)
    width = ink_bbox_width(binary)
    proj = horizontal_projection(binary)
    return binary, proj, width


def rank_ca_ga(
    image: np.ndarray,
    candidates: list[str],
    truth_df: pd.DataFrame,
    *,
    ocr_text: str = "",
    known_chars: str = "",
    ca_steps: int = 3,
    use_ga: bool = True,
    top_n: int = 10,
    force_invert: bool | None = None,
) -> tuple[pd.DataFrame, np.ndarray]:
    """Rank candidates; return (results_df, ca_binary_preview)."""
    binary, proj, width = prepare_ink(image, ca_steps=ca_steps, force_invert=force_invert)
    px_per_char = max(width / 8.0, 8.0) if width else 14.0

    if use_ga and candidates:
        pop = run_ga(
            candidates,
            proj,
            width,
            ocr_text=ocr_text,
            known_chars=known_chars,
        )
        # Keep best fitness per name across the population (scale/shift genes)
        scored_map: dict[str, float] = {}
        for ind in pop:
            name = candidates[ind.name_idx]
            sc = fitness(
                name,
                proj,
                width,
                ocr_text=ocr_text,
                known_chars=known_chars,
                scale=ind.scale,
                x_shift=ind.x_shift,
                px_per_char=px_per_char,
            )
            if name not in scored_map or sc > scored_map[name]:
                scored_map[name] = sc
        scored = sorted(scored_map.items(), key=lambda x: x[1], reverse=True)
    else:
        # exhaustive with default scale/shift but length-aware px_per_char
        scored = []
        for name in candidates:
            sc = fitness(
                name,
                proj,
                width,
                ocr_text=ocr_text,
                known_chars=known_chars,
                px_per_char=px_per_char,
            )
            scored.append((name, sc))
        scored.sort(key=lambda x: x[1], reverse=True)

    meta = truth_df.drop_duplicates(subset=["street_name"]).set_index("street_name")
    rows = []
    for name, sc in scored[:top_n]:
        info = meta.loc[name] if name in meta.index else None
        rows.append(
            {
                "rank": len(rows) + 1,
                "street_name": name,
                "match_pct": round(float(sc) * 100.0, 1),
                "ocr_text": ocr_text,
                "year_ranges": "" if info is None else info.get("year_ranges", ""),
                "exists_today": "" if info is None else info.get("exists_today", ""),
                "same_as": "" if info is None else info.get("same_as", ""),
                "method": "ca_ga" if use_ga else "ca_score_all",
            }
        )
    return pd.DataFrame(rows), binary
