# Kowel street-name OCR

Streamlit tool for reading rotated street labels on historical maps of Kowel.

## Workflow

1. Upload a map image (**Navigate** mode).
2. **Mouse wheel** to zoom, **middle-mouse drag** to pan (left-drag also pans). Frame the street name.
3. Click **Lock view for drawing** (switches to **Draw** mode).
4. **Draw baseline** — line under the street name (any angle).
5. Switch to **Move band** — click the orange/green box and drag / resize / rotate it (or use Nudge X/Y). Set initial height with the Band height slider before moving.
6. In **Crop & transform**, flip / rotate / fine-rotate / invert until the name reads upright left-to-right.
7. Choose a **Ranker**, leave **Handwriting / low-quality mode** on for degraded scans, run recognition, review the **top 10** matches.

### Navigation

| Input | Effect |
| --- | --- |
| Mouse wheel | Zoom in / out (Leaflet) |
| Middle mouse drag | Pan |
| Left mouse drag | Pan (Leaflet default) |
| Lock view for drawing | Freeze the visible region for the line canvas |
| Unlock view | Return to Navigate (clears baseline) |

### Transform controls

| Control | Effect |
| --- | --- |
| ⟲ / ⟳ 90°, 180° | Quarter-turn the deskewed crop |
| Flip H / Flip V | Mirror horizontally or vertically |
| Fine rotate | ±45° continuous correction |
| Invert | Useful for light text on dark map ink |
| Reset | Clear all transforms (keeps the band selection) |

Transforms apply only to the OCR crop — you do not need to redraw the baseline.

## Run

```bash
cd apps/street_name_ocr
pip install -r requirements.txt
streamlit run app.py
```

`requirements.txt` pins `streamlit<1.40` with `streamlit-drawable-canvas==0.9.3` (newer Streamlit breaks that canvas package).

First EasyOCR run downloads Polish/English recognition models (can take a few minutes).

## Notes

- Use the canvas **line** tool (not freestyle).
- Toggle “Text is above the baseline” if the band appears on the wrong side of your under-line.
- `exists_today` / `year_ranges` in the results come from the truth table; this app does not write back to it.
- Matching is fuzzy (`rapidfuzz` WRatio) on diacritic-folded names; OCR alone is often imperfect on map type.

### Handwriting / low-quality mode

On by default. Instead of running EasyOCR once on a single CLAHE-upscaled crop, it:

1. Builds 4 preprocessing renderings of the crop — CLAHE+sharpen, denoise+CLAHE+sharpen,
   an inverted-polarity version, and an adaptive-threshold binarization — and adaptively
   upscales small bands so lettering reaches a usable pixel height for the recognizer.
2. Runs EasyOCR (beam-search decoding, allowlisted to the street-name alphabet by default)
   on all four, instead of just one fixed pipeline.
3. Ranks the truth table against *every* reading and keeps each candidate's best score,
   rather than betting the whole result on one preprocessing choice.
4. Never silently returns empty OCR text — if nothing clears the confidence floor, the
   single best low-confidence guess is kept so the fuzzy ranker still has something to
   work with. All readings used are shown in an expander under the results table.

Turn it off for clean, printed labels where the single-pipeline path is faster.

### Experimental CA + GA ranker

For **degraded / partial** labels where EasyOCR fails:

1. **Cellular automata** cleans the binary ink (remove speckles, bridge small gaps).
2. Fitness vs each truth-table name uses a 1D ink projection + length prior (+ optional OCR / known characters).
3. A **genetic algorithm** searches name index + scale/shift — or tick **Score all** for exhaustive ranking (~160 names).

This is closed-set matching, not a from-scratch OCR engine. Use **Blend both** to combine EasyOCR fuzzy scores with CA/GA fitness.
