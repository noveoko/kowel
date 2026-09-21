# Kowel streets truth table

File: `archives/normalized/kowel_streets_truth_table.csv`

## Columns

- `street_id` — stable id (`st:` + hash of folded name)
- `corridor_id` — `same_as` corridor when set, else `street_id`
- `street_name` — one historical name form per row (Polish preferred)
- `year_ranges` — attestation years from repo sources (`1917;1929;1938`)
- `exists_today` — `y`/`n` if the **physical corridor** still appears on a modern map of Kovel
- `same_as` — shared corridor id linking renames/aliases
- `notes` — rename / matching notes
- `sources` — local datasets that attested the name

## How it was built

1. Seed names from `streets.csv`, `street_names.txt`, `archives/landmark_map_gold_standard/voting_districts_kowel.csv`, `doctors_resident_in_kowel.csv`.
2. Add attestation years from 1929 directories and 1938 phone/normalized listings (match-only; OCR junk not added as new streets).
3. Add 1917 occupation names from `archives/ww1_grain_distribution_kowel.csv` and selected Yiddish/Hebrew aliases.
4. Set `exists_today` using OpenStreetMap named highways in bbox 51.18–51.25N, 24.66–24.78E (see `kovel_osm_streets.json`), Polish→Ukrainian cognate hints, and landmark status when available.

## Limits

- Attestation years ≠ full official rename gazetteer.
- Many interwar streets survive under different Ukrainian names; where no cognate match was found, `exists_today=y` is a corridor presumption for the continuous urban fabric (see notes).
- Unmapped 1917 occupation labels are `exists_today=n` for the label itself.

Regenerate: `python archives/build_streets_truth_table.py`
