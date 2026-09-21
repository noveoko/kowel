# Data inventory

Status of structured files in this repository. Prefer **canonical** files when
building maps or tools. Seed files are useful sources that have not been merged
into a single people/building table yet (that merge is a later phase).

License and reuse: [LICENSE](../LICENSE), [LICENSE-DATA](../LICENSE-DATA).
Names of victims and wanted persons: [NAMES.md](../NAMES.md).

Row counts are data rows (header excluded), measured 2026-09-21.

## Canonical (read these first)

| File | Rows | Columns | Source | Notes |
| --- | ---: | --- | --- | --- |
| [normalized/kowel_streets_truth_table.csv](normalized/kowel_streets_truth_table.csv) | 213 | `street_name`, `year_ranges`, `exists_today`, `same_as`, `notes`, `sources` | Seed lists + 1929/1938 attestations + OSM | Closed street list. Notes: [kowel_streets_truth_table.md](normalized/kowel_streets_truth_table.md). Rebuild: `python archives/build_streets_truth_table.py` |
| [normalized/kovel_osm_streets.json](normalized/kovel_osm_streets.json) | — | OSM named highways | OpenStreetMap, bbox 51.18–51.25N, 24.66–24.78E | Input to `exists_today` |
| [database of kowel crime/data/kowel_criminal_database/kowel_criminal_database.csv](database%20of%20kowel%20crime/data/kowel_criminal_database/kowel_criminal_database.csv) | 464 | Name, age/birth, address, charge, `kowel_link`, `object_id`, issue, `source_url`, excerpt | Polona *Gazeta Śledcza* OCR | City-tied wanted notices (residence, wanted-by, arrest, offence, or victim in Kowel city). Residents-only subset: `kowel_criminal_database_residents.csv` (123) |
| [database of kowel crime/data/obwieszczenia_publiczne/kowel_businesses.csv](database%20of%20kowel%20crime/data/obwieszczenia_publiczne/kowel_businesses.csv) | 698 | firm, type, streets, owner, register, `object_id`, `source_url` | Polona *Obwieszczenia Publiczne* | Commercial register pairs in Kowel |
| [database of kowel crime/data/obwieszczenia_publiczne/kowel_snippets.csv](database%20of%20kowel%20crime/data/obwieszczenia_publiczne/kowel_snippets.csv) | 4257 | `object_id`, issue, page, highlight, `source_url` | Same harvest | Page hits for `"w Kowlu"` |
| [landmark_map_gold_standard/nodes.csv](landmark_map_gold_standard/nodes.csv) | 367 | `Id`, `Label`, `x`, `y`, `pixel_x`, `pixel_y` | Manual digitizer | Schematic map graph (in progress) |
| [landmark_map_gold_standard/edges.csv](landmark_map_gold_standard/edges.csv) | 253 | `Id`, `Source`, `Target`, `Label`, `Type`, `Weight` | Same | Street segments on the schematic |
| [landmark_map_gold_standard/fuzzy_nodes.csv](landmark_map_gold_standard/fuzzy_nodes.csv) | 367 | lon/lat, landmark match, confidence | Georeference scripts | Geographic working copy of the nodes |
| [../GIS/kowel_streets15.kmz](../GIS/kowel_streets15.kmz) | — | Google Earth | Manual | Work-in-progress 1919–1939 streets and ~130 buildings |
| [landmark_map_gold_standard/voting_districts_kowel.csv](landmark_map_gold_standard/voting_districts_kowel.csv) | 135 | `district_no`, `city`, `polling_place`, `polling_address`, `street`, `qualifier` | Polona obwieszczenie 28 Sep 1938 | Live copy. `build_streets_truth_table.py` still opens a missing root `kowel_voting_districts.csv` |
| [../1929_business_directory.csv](../1929_business_directory.csv) | 519 | `Section`, `Name`, `Address` | 1929 Polish business directory | Narrative twin: [1929_business_directory.md](../1929_business_directory.md) |
| [../kowel_residents_1938.csv](../kowel_residents_1938.csv) | 186 | phone, names, type, industry, street, number | 1938 telephone book | Thin resident/business listing |

There is **no** single canonical `people.csv` or `buildings.csv` yet. Use the seed files below until Phase 2.

## Map and buildings (seed)

| File | Rows | Status | What it is |
| --- | ---: | --- | --- |
| [landmark_map_gold_standard/](landmark_map_gold_standard/readme.md) | — | working gold standard | Digitizer HTML, georeference, snap-to-streets, KMZ export |
| [landmark_map_gold_standard/fuzzy_nodes_snapped.csv](landmark_map_gold_standard/fuzzy_nodes_snapped.csv) | 367 | derived | Nodes snapped toward OSM streets |
| [landmark_map_gold_standard/fuzzy_edges.csv](landmark_map_gold_standard/fuzzy_edges.csv) | 253 | derived | Edges with lon/lat |
| [landmark_map_gold_standard/landmarks_transcribed.csv](landmark_map_gold_standard/landmarks_transcribed.csv) | 150 | seed | Landmark names from the map |
| [landmark_map_gold_standard/kowel_markers_pl.csv](landmark_map_gold_standard/kowel_markers_pl.csv) | 83 | seed | Ukrainian marker text + Polish translation |
| [landmark_map_gold_standard/project progress/](landmark_map_gold_standard/project%20progress/) | — | snapshot | Older digitizer export; do not edit |
| [../maps/kowel_buildings.csv](../maps/kowel_buildings.csv) | 71 | seed | Building, address, purpose, destroyed Y/N (many addresses unspecified) |
| [../maps/kowel_landmarks_index.csv](../maps/kowel_landmarks_index.csv) | 61 | seed | Indexed landmarks with destruction/post-war notes |
| [map_index.csv](map_index.csv) | 61 | duplicate | Same index without extra columns |
| [known_buildings.csv](known_buildings.csv) | 52 | seed | Name, location, year, events, visual description |
| [kovel_map_markers.csv](kovel_map_markers.csv) | 69 | seed | Marker index, Ukrainian, Polish |
| [locations_on_hebrew_map_kowel.csv](locations_on_hebrew_map_kowel.csv) | 39 | seed | Prayer houses and sources |
| [places_described.csv](places_described.csv) | 99 | seed | Named places inside city limits |
| [building_desctruction_key.csv](building_desctruction_key.csv) | 9 | seed | Destruction-map legend |
| [../archive/landmarks_to_verify.csv](../archive/landmarks_to_verify.csv) | 25 | working | Lat/lon candidates still to check |
| [../building_coordinates.txt](../building_coordinates.txt) | — | seed | Loose coordinate notes |
| [../maps/correct-locations-kowel.geojson](../maps/correct-locations-kowel.geojson) | — | working | Point corrections |

## Streets (canonical vs older lists)

| File | Rows | Status | What it is |
| --- | ---: | --- | --- |
| [normalized/kowel_streets_truth_table.csv](normalized/kowel_streets_truth_table.csv) | 213 | **canonical** | Attested names, years, corridor ids |
| [../streets.csv](../streets.csv) | 146 | seed / older | `name`, `id`, coordinates, years, addresses, voting district |
| [../street_names.txt](../street_names.txt) | — | seed | 1929 phone book + 1938 polling notice compilation |
| [../referenced_streets.txt](../referenced_streets.txt) | — | derived | Cross-referenced names |
| [../Kowel Streets 1929 Phone Book - Polish Streets.csv](../Kowel%20Streets%201929%20Phone%20Book%20-%20Polish%20Streets.csv) | 175 | seed | Polish / Ukrainian / Russian name forms |
| [../streets_by_business_address_count.csv](../streets_by_business_address_count.csv) | 37 | derived | Counts from the 1929 directory |
| [ww1_grain_distribution_kowel.csv](ww1_grain_distribution_kowel.csv) | 13 | seed | 1917 occupation street names (feeds truth table) |
| [code/visualize_streets/streets.csv](../code/visualize_streets/streets.csv) | 519 | duplicate | Copy of the 1929 directory CSV |

## People (all seed; no unified person id)

Treat each file as a **source extract**. Do not merge rows into one identity without a shared given name, surname, and a date or address. See [NAMES.md](../NAMES.md).

| File | Rows | Likely origin | Columns (short) |
| --- | ---: | --- | --- |
| [people_living_in_Kowel.csv](people_living_in_Kowel.csv) | 231 | Polish civil-style list | Nazwisko, Imię, maiden, birth/death, parents |
| [normalized/people_and_birth_places.csv](normalized/people_and_birth_places.csv) | 268 | Mixed (incl. Auschwitz surnames + residents) | first_name, last_name, birth_place, residence, notes |
| [kowel_births.csv](kowel_births.csv) | 1000 | Arolsen-style extract | Signature, names, birth, prisoner #, last residence… |
| [kowel_births_1843_1945.csv](kowel_births_1843_1945.csv) | 1000 | Same schema as `kowel_births.csv` | Treat as duplicate until diffed |
| [Auschwitz_prisoners_born_in_kowel.csv](Auschwitz_prisoners_born_in_kowel.csv) | 37 | Auschwitz birthplace filter | surname, birth_year, birthplace |
| [kowel_born_deported_east.csv](kowel_born_deported_east.csv) | 14 | Polish deportee list | Nazwisko, Imię, father, year |
| [polish_military_born_in_kowel.csv](polish_military_born_in_kowel.csv) | 111 | Military records | names, father, birth, signature |
| [geneva_refugees_ww2.csv](geneva_refugees_ww2.csv) | 25476 | Geneva WW2 registrations | Surname, Name, DOB, nationality — **global list**, not Kowel-only |
| [ship_passengers_born_in_kowel.csv](ship_passengers_born_in_kowel.csv) | 1 | Passenger list | One documented row in-repo |
| [../kowel_residents_1938.csv](../kowel_residents_1938.csv) | 186 | Phone book | See canonical table |
| [../doctors_resident_in_kowel.csv](../doctors_resident_in_kowel.csv) | 18 | 1920 directory ([Lublin DL](https://bc.wbp.lublin.pl/dlibra/publication/edition/17315)) | surname, city, street, number |
| [35M_people.txt](35M_people.txt) | — | Unspecified name dump | Filename is misleading; short surname list |
| [kowel_surnames.txt](kowel_surnames.txt) | — | Derived surname list | |

`geneva_refugees_ww2.csv` is large and mostly people with no Kowel tie. Filter before joining.

## Firms and directories

| File | Rows | Status | What it is |
| --- | ---: | --- | --- |
| [../1929_business_directory.csv](../1929_business_directory.csv) | 519 | canonical-for-1929 | Section / name / address |
| [1929 Kowel Business Directory (Digitized) - 1929 Business Listing.csv](1929%20Kowel%20Business%20Directory%20(Digitized)%20-%201929%20Business%20Listing.csv) | 1275 | seed | Digitized listing (Business Name, Owner, Address); denser, dirtier |
| [normalized_directory_kowel.csv](normalized_directory_kowel.csv) | 723 | derived | Normalized phone/directory rows |
| [1930_telephone_directory.csv](1930_telephone_directory.csv) | 1018 | seed | City, entity, role, address (may include other towns) |
| [kowel_business_info.csv](kowel_business_info.csv) | 698 | **duplicate** | Copy of harvest `kowel_businesses.csv` — edit the harvest file |
| [../archive/lucka_businesses.csv](../archive/lucka_businesses.csv) | 23 | seed | Łucka Street firms |
| [../industries_in_kowel_1929.csv](../industries_in_kowel_1929.csv) | 77 | seed | Polish / French / English industry labels (needs checking) |
| [insurance_accounts_kowel.csv](insurance_accounts_kowel.csv) | 25 | seed | ID, name, address, business type |
| [przeglad_wolynski_licytacja_1929.csv](przeglad_wolynski_licytacja_1929.csv) | 123 | seed | 1929 *Przegląd Wołyński* auction / mortgage notices |
| [Kowel_1929_1930_Merged.xlsx](Kowel_1929_1930_Merged.xlsx) | — | working spreadsheet | Merged 1929/1930 directory work |

## Crime and gazette harvest

Working directory: [database of kowel crime/](database%20of%20kowel%20crime/README.md).

| File | Rows | Status | What it is |
| --- | ---: | --- | --- |
| `.../kowel_criminal_database/kowel_criminal_database.csv` | 464 | **canonical** | City-tied wanted-person rows + `kowel_link` |
| `.../kowel_criminal_database/kowel_criminal_database_residents.csv` | 123 | subset | Last-address-in-Kowel only |
| `.../kowel_criminal_database/kowel_associates.csv` | 464 | working | Same harvest with associate tagging |
| [kowel_criminal_database.csv](kowel_criminal_database.csv) | 123 | **stale duplicate** | Older residents-only copy at `archives/` root — do not edit |
| `.../data/gazeta_sledcza/` | 11 | sample harvest | Single-issue / limited run |
| `.../data/gazeta_sledcza_limit2/` | 0 data | smoke test | Empty CSVs + 2 OCR files |
| `.../data/overlap_crime_register.csv` | 6 | derived | Surname overlap vs business register (no same-person hits) |
| `.../sample_output.csv` | 10 | fixture | Parser sample for 1930-12-31 |
| Harvest `ocr/*.txt` | ~1160 files | working cache | Regenerable from Polona; keep CSVs + `manifest.jsonl` as the citable product |

## News and narrative

| File | Rows | Status |
| --- | ---: | --- |
| [newspapers/news.csv](newspapers/news.csv) | 369 | seed clippings |
| [news_clippings/events.csv](news_clippings/events.csv) | 5 | trilingual event blurbs |
| [kowel_book_1936/bibliography.csv](kowel_book_1936/bibliography.csv) | 10 | 1936 book bibliography |
| [kowel_book_1936/building-info.md](kowel_book_1936/building-info.md) | — | building notes from that book |

## How to add a table

1. Put source extracts under `archives/` with a date and source URL in the file or a sidecar note.
2. If it is a street, person, firm, or building that tools should read, say so in this file and point at a **canonical** path.
3. Do not copy a canonical CSV to the repo root “for convenience”; link it instead.
4. Keep `object_id` / archival signature / `source_url` on harvested rows.
