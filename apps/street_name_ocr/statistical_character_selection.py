"""Filter street-name candidates by known letters, length, and noisy OCR."""

import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher

import pandas as pd
import streamlit as st

from ocr_rank import (
    DEFAULT_TRUTH_TABLE,
    _DIACRITIC,
    candidate_names,
    load_truth_table,
)


st.set_page_config(
    page_title="String Candidate Eliminator",
    page_icon="🔎",
    layout="wide",
)

st.title("🔎 String Candidate Eliminator")
st.caption(
    "Filter a list of possible strings using known letters, length, "
    "positions, and fuzzy/statistical matching."
)


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def normalize(s: str) -> str:
    """Fold Polish diacritics, then keep letters and digits only."""
    s = (s or "").strip().translate(_DIACRITIC)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-zA-Z0-9]", "", s).lower()


def required_letters_match(candidate: str, required: str) -> bool:
    """
    Every occurrence entered by the user must exist in the candidate.

    Example:
        required = "letter"
        candidate must contain l,e,t,t,e,r
    """
    candidate_counts = Counter(candidate)
    required_counts = Counter(normalize(required))

    return all(
        candidate_counts[ch] >= count
        for ch, count in required_counts.items()
    )


def positional_match(candidate: str, pattern: str) -> bool:
    """
    Pattern example:
        _a__r_

    '_' means unknown.
    """
    pattern = normalize_pattern(pattern)

    if len(candidate) != len(pattern):
        return False

    for candidate_char, pattern_char in zip(candidate, pattern):
        if pattern_char != "_" and candidate_char != pattern_char:
            return False

    return True


def normalize_pattern(pattern: str) -> str:
    """Keep letters/numbers/_ from a positional pattern (diacritics folded)."""
    s = (pattern or "").strip().translate(_DIACRITIC)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return "".join(c for c in s.lower() if c.isalnum() or c == "_")


def fuzzy_score(a: str, b: str) -> float:
    if not a or not b:
        return 0.0

    return SequenceMatcher(None, a, b).ratio()


def length_score(length: int, target: int, tolerance: int) -> float:
    distance = abs(length - target)

    if distance == 0:
        return 1.0

    if distance > tolerance:
        return 0.0

    return 1 - (distance / (tolerance + 1))


def letter_coverage(candidate: str, observed: str) -> float:
    """
    Measures how many observed letters occur in candidate.

    Unlike required_letters_match(), this is useful for ranking
    candidates when the input may itself contain OCR mistakes.
    """
    observed = normalize(observed)

    if not observed:
        return 1.0

    candidate_counts = Counter(candidate)
    observed_counts = Counter(observed)

    matched = 0
    total = sum(observed_counts.values())

    for char, count in observed_counts.items():
        matched += min(candidate_counts.get(char, 0), count)

    return matched / total


def score_candidate(
    candidate,
    target_length,
    tolerance,
    required,
    pattern,
    noisy_ocr,
):
    scores = {}

    scores["length"] = length_score(
        len(candidate),
        target_length,
        tolerance,
    )

    scores["letters"] = letter_coverage(
        candidate,
        required,
    )

    scores["position"] = (
        1.0
        if pattern and positional_match(candidate, pattern)
        else 0.0
        if pattern
        else 1.0
    )

    scores["ocr"] = fuzzy_score(
        candidate,
        normalize(noisy_ocr),
    ) if noisy_ocr else 0.0

    # Weights can later be exposed in the UI.
    weighted = (
        scores["length"] * 0.30
        + scores["letters"] * 0.35
        + scores["position"] * 0.20
        + scores["ocr"] * 0.15
    )

    return weighted, scores


# ---------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------

st.sidebar.header("Candidate list")

use_truth = st.sidebar.checkbox(
    "Use Kowel streets truth table",
    value=True,
    help=str(DEFAULT_TRUTH_TABLE),
)
include_1917 = st.sidebar.checkbox(
    "Include 1917 occupation names",
    value=False,
    disabled=not use_truth,
)

uploaded = st.sidebar.file_uploader(
    "Upload extra candidate strings",
    type=["txt", "csv"],
)

candidate_text = st.sidebar.text_area(
    "Or paste extra candidates",
    placeholder="apple\napricot\norange\npear\n...",
    height=180,
)

raw_candidates: list[str] = []

if use_truth:
    try:
        truth = load_truth_table()
        raw_candidates.extend(
            candidate_names(truth, include_1917=include_1917)
        )
    except (OSError, ValueError) as exc:
        st.sidebar.error(f"Could not load truth table: {exc}")

if uploaded is not None:
    if uploaded.name.endswith(".csv"):
        df = pd.read_csv(uploaded)
        col = "street_name" if "street_name" in df.columns else df.columns[0]
        raw_candidates.extend(df[col].dropna().astype(str).tolist())
    else:
        raw_candidates.extend(
            uploaded.read()
            .decode("utf-8", errors="ignore")
            .splitlines()
        )

if candidate_text.strip():
    raw_candidates.extend(candidate_text.splitlines())

# Display original names; match on folded alphanumeric keys.
candidates: list[str] = []
seen_keys: set[str] = set()
for name in raw_candidates:
    name = name.strip()
    key = normalize(name)
    if not key or key in seen_keys:
        continue
    seen_keys.add(key)
    candidates.append(name)

st.sidebar.metric("Candidates loaded", len(candidates))
if use_truth:
    st.sidebar.caption(f"Truth table: `{DEFAULT_TRUTH_TABLE.name}`")


# ---------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------

st.header("What do you know about the string?")

col1, col2 = st.columns(2)

with col1:
    target_length = st.number_input(
        "Expected length",
        min_value=1,
        max_value=200,
        value=8,
    )

with col2:
    tolerance = st.number_input(
        "Length tolerance",
        min_value=0,
        max_value=20,
        value=2,
        help="Candidates outside this range are eliminated.",
    )

required = st.text_input(
    "Letters you are certain are present",
    placeholder="e.g. a r t",
    help="Enter letters that you know occur somewhere in the string.",
)

pattern = st.text_input(
    "Known positions (optional)",
    placeholder="e.g. __a_r__",
    help="Use _ for unknown characters.",
)

noisy_ocr = st.text_input(
    "Noisy OCR result (optional)",
    placeholder="e.g. ap?le",
    help="Useful when the source text is badly cropped or degraded.",
)


# ---------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------

if st.button("Find candidates", type="primary"):

    if not candidates:
        st.warning("Load or paste a candidate list first.")
        st.stop()

    required = normalize(required)
    pattern = normalize_pattern(pattern)

    filtered = []

    for display in candidates:
        key = normalize(display)

        # Hard length filter (letter/digit count after folding).
        if abs(len(key) - target_length) > tolerance:
            continue

        # Hard positional filter.
        if pattern and not positional_match(key, pattern):
            continue

        # Confirmed letters are hard constraints.
        if required and not required_letters_match(key, required):
            continue

        score, components = score_candidate(
            key,
            target_length,
            tolerance,
            required,
            pattern,
            noisy_ocr,
        )

        filtered.append({
            "candidate": display,
            "score": score,
            "length_score": components["length"],
            "letter_score": components["letters"],
            "position_score": components["position"],
            "ocr_score": components["ocr"],
        })

    results = pd.DataFrame(filtered)

    if results.empty:
        st.warning(
            "No candidates survived the hard filters. "
            "Try increasing the length tolerance or removing "
            "a letter/position constraint."
        )
        st.stop()

    results = results.sort_values(
        "score",
        ascending=False,
    ).reset_index(drop=True)

    results.index += 1

    # -----------------------------------------------------------------
    # Results
    # -----------------------------------------------------------------

    st.success(
        f"{len(results)} candidate(s) survived "
        f"from {len(candidates)}."
    )

    st.subheader("Most likely candidates")

    display = results.copy()

    display["score"] = (
        display["score"] * 100
    ).round(1)

    display["length_score"] = (
        display["length_score"] * 100
    ).round(1)

    display["letter_score"] = (
        display["letter_score"] * 100
    ).round(1)

    display["position_score"] = (
        display["position_score"] * 100
    ).round(1)

    display["ocr_score"] = (
        display["ocr_score"] * 100
    ).round(1)

    display.columns = [
        "Candidate",
        "Overall %",
        "Length %",
        "Letters %",
        "Positions %",
        "OCR %",
    ]

    st.dataframe(
        display,
        use_container_width=True,
    )

    # Highlight top candidates.
    st.subheader("Shortlist")

    for _, row in results.head(10).iterrows():
        st.markdown(
            f"### `{row['candidate']}` — "
            f"{row['score'] * 100:.1f}%"
        )

        st.progress(
            min(max(row["score"], 0), 1)
        )

        st.caption(
            f"Length: {row['length_score'] * 100:.0f}% · "
            f"Letters: {row['letter_score'] * 100:.0f}% · "
            f"Position: {row['position_score'] * 100:.0f}% · "
            f"OCR: {row['ocr_score'] * 100:.0f}%"
        )
