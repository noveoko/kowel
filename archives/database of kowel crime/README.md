# Gazeta Śledcza and Obwieszczenia harvest

Polona search-service clients and parsers for Kowel-tied wanted-person notices
(*Gazeta Śledcza*) and commercial-register snippets (*Obwieszczenia Publiczne*).

Canonical outputs and how they relate to other tables: [../DATA.md](../DATA.md).
How to treat names: [../../NAMES.md](../../NAMES.md).

## Run (from this directory)

```bash
uv sync
uv run python harvest_gazeta.py --out data/kowel_criminal_database --sleep 0.35
uv run python harvest_obwieszczenia.py --out data/obwieszczenia_publiczne --sleep 0.4
```

Resume-safe: skip existing OCR, write after each issue, `HARVEST_OK` / `HARVEST_FAIL`
sentinels. Do not run two heavy Polona harvests at once.

Useful flags: `--limit N`, `--object-id`, `--all-issues`, `--no-skip-existing`,
`--snippets-only` (Obwieszczenia).

## Layout

| Path | Role |
| --- | --- |
| `polona_client.py` | Current API (`search-service`). Use this. |
| `polona_bulk_download.py` | Deprecated wrapper |
| `gazeta_parser.py` | Last-address / city-tied wanted entries from OCR |
| `obwieszczenia_parser.py` | Firm + owner pairs |
| `extract_kowel_associates.py` | Extra Kowel tags (court, county, born, …) |
| `compare_crime_register.py` | Name overlap vs business CSV |
| `sample_input.txt` / `sample_output.csv` | Parser fixture (1930-12-31) |
| `sample_obwieszczenia_1924.txt` | Register fixture (16 Aug 1924) |

Street names stay in the grammatical case of the OCR. Unknown k.k. articles
are labelled for hand check, not guessed.

`data/gazeta_sledcza/` and `data/gazeta_sledcza_limit2/` are sample/smoke runs.
Edit `data/kowel_criminal_database/` and `data/obwieszczenia_publiczne/`.
