"""EasyOCR on deskewed crops + fuzzy ranking against the street truth table."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRUTH_TABLE = REPO_ROOT / "archives" / "normalized" / "kowel_streets_truth_table.csv"

_DIACRITIC = str.maketrans(
    {
        "ą": "a",
        "ć": "c",
        "ę": "e",
        "ł": "l",
        "ń": "n",
        "ó": "o",
        "ś": "s",
        "ź": "z",
        "ż": "z",
        "Ą": "A",
        "Ć": "C",
        "Ę": "E",
        "Ł": "L",
        "Ń": "N",
        "Ó": "O",
        "Ś": "S",
        "Ź": "Z",
        "Ż": "Z",
    }
)


def fold_name(s: str) -> str:
    s = (s or "").strip().translate(_DIACRITIC)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"^(ul\.?|ulica|al\.?|aleja|pl\.?|plac)\s+", "", s)
    s = re.sub(r"[^a-z0-9\s\-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def load_truth_table(path: Path | None = None) -> pd.DataFrame:
    path = path or DEFAULT_TRUTH_TABLE
    df = pd.read_csv(path)
    if "street_name" not in df.columns:
        raise ValueError(f"Truth table missing street_name column: {path}")
    return df


def candidate_names(df: pd.DataFrame, include_1917: bool = False) -> list[str]:
    names = []
    for name in df["street_name"].astype(str):
        if not include_1917 and name.endswith("(1917)"):
            continue
        names.append(name)
    # unique preserve order
    seen = set()
    out = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def build_allowlist(candidates: list[str]) -> str:
    """Character set worth letting EasyOCR output, derived from the closed
    candidate list itself.

    This is one of the highest-leverage changes for a closed-vocabulary
    problem like street-name OCR: without it, EasyOCR is free to "recognize"
    digits, punctuation, or Latin letters that never appear in any candidate
    name, which is a common way handwriting gets misread. Restricting the
    decoder's alphabet to exactly what's possible removes a whole class of
    errors for free.
    """
    chars: set[str] = set()
    for name in candidates:
        chars.update(name)
        chars.update(name.upper())
        chars.update(name.lower())
    chars.update(" -.")
    chars.discard("\n")
    chars.discard("\t")
    return "".join(sorted(chars))


def run_ocr(
    reader,
    image: np.ndarray,
    min_conf: float = 0.15,
    allowlist: str | None = None,
    decoder: str = "beamsearch",
    contrast_ths: float = 0.05,
    adjust_contrast: float = 0.7,
    text_threshold: float = 0.5,
    low_text: float = 0.3,
) -> tuple[str, list[dict]]:
    """Run EasyOCR; return joined text and per-box details.

    ``image`` may be gray or BGR. EasyOCR expects RGB or gray ndarray.

    Defaults are tuned for degraded/handwritten map lettering rather than
    EasyOCR's scene-text-friendly defaults:

    - ``decoder="beamsearch"`` scores whole-word sequences instead of
      greedily picking each character, which recovers more on messy strokes.
    - ``contrast_ths``/``adjust_contrast`` make EasyOCR re-run its own
      contrast boost more eagerly on low-contrast crops (faint pencil,
      washed-out scans).
    - ``min_conf`` is lower than EasyOCR's usual comfort zone, and if
      *nothing* clears it we still fall back to the single best detection
      rather than returning empty text — a low-confidence guess is more
      useful to the fuzzy ranker than nothing, since ranking is checked
      against a closed list of ~160 real names anyway.
    """
    if image.ndim == 2:
        rgb = image
    else:
        # assume BGR from OpenCV
        import cv2

        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    kwargs: dict = dict(
        decoder=decoder,
        contrast_ths=contrast_ths,
        adjust_contrast=adjust_contrast,
        text_threshold=text_threshold,
        low_text=low_text,
        paragraph=False,
    )
    if allowlist:
        kwargs["allowlist"] = allowlist

    results = reader.readtext(rgb, **kwargs)
    parts: list[str] = []
    details: list[dict] = []
    for bbox, text, conf in results:
        conf_f = float(conf)
        details.append({"text": text, "confidence": conf_f, "bbox": bbox})
        if conf_f >= min_conf and text.strip():
            parts.append(text.strip())

    joined = " ".join(parts).strip()
    if not joined and details:
        best = max(details, key=lambda d: d["confidence"])
        if best["text"].strip():
            joined = best["text"].strip()
    return joined, details


def run_ocr_ensemble(
    reader,
    variants: list[tuple[str, np.ndarray]],
    min_conf: float = 0.15,
    allowlist: str | None = None,
    decoder: str = "beamsearch",
) -> tuple[list[tuple[str, float, str]], list[dict]]:
    """Run OCR across several preprocessed renderings of the same crop.

    Returns ``(readings, all_details)`` where ``readings`` is a list of
    ``(text, confidence, source_label)``. The caller ranks against *every*
    reading and keeps each candidate street's best score, which is far more
    forgiving than betting the whole result on one fixed preprocessing
    pipeline — a crop that reads badly after CLAHE alone often reads fine
    after denoise+sharpen or adaptive threshold, and vice versa.
    """
    readings: list[tuple[str, float, str]] = []
    all_details: list[dict] = []
    for label, img in variants:
        joined, details = run_ocr(
            reader, img, min_conf=min_conf, allowlist=allowlist, decoder=decoder
        )
        for d in details:
            d["source"] = label
        all_details.extend(details)
        if joined:
            conf = max((d["confidence"] for d in details), default=0.0)
            readings.append((joined, conf, label))
    return readings, all_details


def rank_streets(
    ocr_text: str,
    candidates: list[str],
    truth_df: pd.DataFrame,
    top_n: int = 10,
) -> pd.DataFrame:
    """Fuzzy-match OCR text against candidate street names; return top_n rows."""
    query = fold_name(ocr_text)
    if not query:
        # empty OCR → return empty ranked frame with schema
        return pd.DataFrame(
            columns=[
                "rank",
                "street_name",
                "match_pct",
                "ocr_text",
                "year_ranges",
                "exists_today",
                "same_as",
                "method",
            ]
        )

    folded_map = {name: fold_name(name) for name in candidates}
    # rapidfuzz extract against folded values, then map back
    # unique folded → prefer first original
    fold_to_name: dict[str, str] = {}
    for name, f in folded_map.items():
        fold_to_name.setdefault(f, name)

    matches = process.extract(
        query,
        list(fold_to_name.keys()),
        scorer=fuzz.WRatio,
        limit=max(top_n * 3, top_n),
    )

    meta = truth_df.drop_duplicates(subset=["street_name"]).set_index("street_name")
    rows = []
    seen_names = set()
    for folded, score, _ in matches:
        name = fold_to_name[folded]
        if name in seen_names:
            continue
        seen_names.add(name)
        info = meta.loc[name] if name in meta.index else None
        rows.append(
            {
                "rank": len(rows) + 1,
                "street_name": name,
                "match_pct": round(float(score), 1),
                "ocr_text": ocr_text,
                "year_ranges": "" if info is None else info.get("year_ranges", ""),
                "exists_today": "" if info is None else info.get("exists_today", ""),
                "same_as": "" if info is None else info.get("same_as", ""),
                "method": "easyocr",
            }
        )
        if len(rows) >= top_n:
            break

    return pd.DataFrame(rows)


def rank_streets_multi(
    ocr_readings: list[str],
    candidates: list[str],
    truth_df: pd.DataFrame,
    top_n: int = 10,
) -> pd.DataFrame:
    """Rank against several OCR readings at once, keeping each candidate
    street's *best* score across all of them.

    Use this instead of ``rank_streets`` whenever more than one OCR reading
    is available (see ``run_ocr_ensemble``). Averaging readings would punish
    a name that one variant nailed and another garbled; taking the max lets
    a single good reading win even if the rest were noise.
    """
    queries = [q for q in (ocr_readings or []) if fold_name(q)]
    if not queries:
        return rank_streets("", candidates, truth_df, top_n=top_n)
    if len(queries) == 1:
        return rank_streets(queries[0], candidates, truth_df, top_n=top_n)

    best: dict[str, tuple[float, str]] = {}
    for q in queries:
        df = rank_streets(q, candidates, truth_df, top_n=len(candidates) or top_n)
        for _, row in df.iterrows():
            name = row["street_name"]
            pct = float(row["match_pct"])
            if name not in best or pct > best[name][0]:
                best[name] = (pct, q)

    meta = truth_df.drop_duplicates(subset=["street_name"]).set_index("street_name")
    ranked = sorted(best.items(), key=lambda kv: kv[1][0], reverse=True)[:top_n]
    rows = []
    for name, (pct, q) in ranked:
        info = meta.loc[name] if name in meta.index else None
        rows.append(
            {
                "rank": len(rows) + 1,
                "street_name": name,
                "match_pct": round(pct, 1),
                "ocr_text": q,
                "year_ranges": "" if info is None else info.get("year_ranges", ""),
                "exists_today": "" if info is None else info.get("exists_today", ""),
                "same_as": "" if info is None else info.get("same_as", ""),
                "method": "easyocr_ensemble",
            }
        )
    return pd.DataFrame(rows)
