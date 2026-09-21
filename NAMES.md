# Names of victims, residents, and wanted persons

This repository reprints names from public historical records so the town of
Kowel can be reconstructed street by street. The lists include Holocaust-era
prisoner and deportee extracts, interwar wanted-person notices, phone books,
and business registers.

## Cite the source

Every reused name should remain attached to the document it came from: gazette
title and date, Polona `object_id` / preview URL, archival signature, or the
local file named in [archives/DATA.md](archives/DATA.md). Do not present a
compiled row as if it were a new primary source.

## What these lists are

- **Wanted-person notices** (*Gazeta Śledcza*) are police publications. A row
  is an OCR’d notice, not a court verdict.
- **Business register snippets** (*Obwieszczenia Publiczne*) are commercial
  filings as printed, with streets often in declined Polish.
- **Prisoner, deportee, refugee, and passenger extracts** are copies from
  named archives (Arolsen and others). They inherit those archives’ errors
  and scope.

OCR will mangle letters (`F\d am`, split surnames). Leave the original string
in the source column; put a corrected reading in a separate field if you add
one.

## What not to add

Do not enrich these tables with living relatives’ addresses, phone numbers,
social-media accounts, or DNA/genealogy matches. The project stops at the
historical record and the reconstruction of the 1918–1945 town.

Do not use wanted-person or victim lists for contemporary accusation,
doxxing, or family contact.

## How to write about people here

Use names as printed, with the source beside them. Prefer quiet, specific
description (address, trade, document date) over dramatizing crime or death.
If a person appears in more than one list, link rows by documented identity
(same given name + surname + a date or address). Surname-only overlap is not
the same person. `archives/normalized/people.csv` follows that rule:
`clustered=y` only when given name, surname, and birth year all match.

## Contact

Corrections from families and researchers: open a GitHub issue on
[noveoko/kowel](https://github.com/noveoko/kowel/issues).
