# Canonical tables

Consumers should read these files, not the scattered extracts under `archives/`
and the repo root.

| File | ID | Rebuild |
| --- | --- | --- |
| `kowel_streets_truth_table.csv` / `streets.csv` | `street_id` | `python archives/build_streets_truth_table.py` then `build_canonical_tables.py` |
| `people.csv` + `people_sources.csv` | `person_id` | `python archives/build_canonical_tables.py` |
| `buildings.csv` | `building_id` | same |
| `firms.csv` | `firm_id` | same |
| `crime.csv` | `crime_id` | same |

People merge only when given name, surname, and birth year all match.
`geneva_refugees_ww2.csv` is not included (almost all rows have no Kowel tie).

Street matching is a folded prefix against the truth table; city names such as
“Kowel” are not treated as streets.
