#!/usr/bin/env python3
"""
Gazeta Śledcza parser
======================
Extracts "wanted persons" entries for KOWEL residents from an OCR'd text
file of a "Gazeta Śledcza" (Polish interwar police gazette) and writes
them to a CSV.

WHY THIS APPROACH
------------------
Every entry in these gazettes follows a fairly rigid template:

    <n>. <reg-id>-IV-<yr>. <Surname Firstname>, s./syn/c. <Father> i
    <Mother>, l. <age> OR ur. ... <birth year>, ... ost. zam. w Kowlu
    przy ul. <street> <no>, ..., osk. z art. <codes> k. k. — <court>, ...

Because it's OCR'd 1930s print, there is noise (misread letters,
line breaks in the middle of words, stray page-footer numbers like
"- 20394 -"). This script:
  1. Strips obvious page-footer artifacts.
  2. Collapses all whitespace/line-breaks so an entry can be matched
     even if it was OCR'd across several physical lines.
  3. Splits the text into entries using the "<n>. <reg-id>-IV-<yr>."
     marker, which is the most OCR-stable anchor in the format.
  4. Keeps only entries whose "last known address" clause says
     "ost. zam. w Kowl..." (i.e. the person's last address was Kowel).
  5. Pulls out Name / Age-or-birth-year / Address / Charge codes with
     targeted regexes.
  6. Maps charge codes to an English description via CHARGE_MAP below.

LIMITATIONS (read before trusting the output)
-----------------------------------------------
- Street names are extracted AS WRITTEN, in whatever grammatical case
  the OCR text used (Polish declines street names). E.g. the source
  text says "ul. Łuckiej 103" (genitive), but the "clean" nominative
  form is "ul. Łucka 103". This script does NOT attempt to un-decline
  Polish street names — that needs real linguistic knowledge, not
  regex, and getting it wrong would silently corrupt data. Review this
  column by hand.
- CHARGE_MAP only has confident entries for the codes shown in your
  example. Anything else comes back as "Unknown - verify (art. NNN)".
  Fill these in yourself from a reliable legal-history source as you
  confirm them — do not guess and hardcode without checking.
- OCR errors will cause some entries to parse only partially (e.g. no
  age found, no charge found). The script does not skip these; it
  fills the field blank and logs a warning line to the console so you
  can find and hand-fix them in the CSV afterward.

USAGE
-----
    python gazeta_parser.py input.txt output.csv

    input.txt  = raw OCR text of one Gazeta Śledcza issue (or several
                 concatenated issues — the entry splitter doesn't care)
    output.csv = where to write the results
"""

import re
import sys
import csv
from pathlib import Path

# --------------------------------------------------------------------------
# 1. CHARGE CODE -> ENGLISH DESCRIPTION MAP
#    Extend this as you confirm more article numbers. Format: the key is
#    the bare article number as a string (e.g. "138"), the value is the
#    English gloss you want in the CSV.
# --------------------------------------------------------------------------
CHARGE_MAP = {
    "51": "Complicity / Aiding and Abetting",
    "138": "Disobedience / Violation of Police Regulations",
    "440": "Forgery",
    "448": "Bribery",
    "581": "Theft",
    "591": "Fraud / Embezzlement",
    "593": "Receiving Stolen Goods",
    # add more as you verify them, e.g.:
    # "154": "...",
    # "464": "...",
    # "530": "...",
}


def charge_lookup(codes):
    """Turn a list of article-number strings into one English label,
    de-duplicated, joined with ' & '. Unknown codes are flagged instead
    of guessed."""
    labels = []
    for c in codes:
        labels.append(CHARGE_MAP.get(c, f"Unknown - verify (art. {c})"))
    seen = set()
    out = []
    for label in labels:
        if label not in seen:
            seen.add(label)
            out.append(label)
    return " & ".join(out)


# --------------------------------------------------------------------------
# 2. TEXT CLEANUP
# --------------------------------------------------------------------------
def clean_text(raw):
    # Drop page-footer artifacts like "- 20394 -" that OCR pulls in
    # mid-document.
    raw = re.sub(r'\n\s*[-—]\s*\d{3,6}\s*[-—]\s*\n', '\n', raw)
    # Collapse ALL whitespace (including newlines) to single spaces so
    # an entry that was OCR'd across several lines still matches as one
    # continuous string.
    raw = re.sub(r'\s+', ' ', raw)
    return raw.strip()


# --------------------------------------------------------------------------
# 3. ENTRY SPLITTING
#    Anchor = "<list-number>. <reg-id>-<roman-numeral>-<year>."
#    e.g.    "1. 45276-1V-30."   (note: IV is often OCR'd as "1V")
# --------------------------------------------------------------------------
ENTRY_START_RE = re.compile(
    r'\b(\d{1,3})\.\s+(\d{4,6}-[A-Za-z0-9]{1,4}-[A-Za-z0-9]{2})\.\s*'
)


def split_entries(cleaned_text):
    matches = list(ENTRY_START_RE.finditer(cleaned_text))
    entries = []

    # Anything before the FIRST recognized header is normally just the
    # section's intro boilerplate ("Następujące osoby..."). But if the
    # very first entry's own header was too garbled to match (e.g. a
    # "30" OCR'd as "3Q"), its content ends up stuck in this preamble
    # and would otherwise be silently lost. Heuristic: if that preamble
    # itself contains a Kowel "ost. zam." clause, warn about it.
    if matches:
        preamble = cleaned_text[: matches[0].start()]
        if KOWEL_RESIDENT_RE.search(preamble):
            print(
                "WARNING: text before the first recognized entry header "
                "mentions a Kowel address, but has no valid entry ID -- "
                "an entry may have been dropped. Check the very start of "
                "the input file by hand:\n"
                f"  ...{preamble[-300:]}"
            )

    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(cleaned_text)
        list_no = m.group(1)
        reg_id = m.group(2)
        body = cleaned_text[start:end].strip()
        entries.append({"list_no": list_no, "reg_id": reg_id, "body": body})
    return entries


# --------------------------------------------------------------------------
# 4. KOWEL-RESIDENT FILTER
#    We only want people whose LAST ADDRESS was in Kowel, i.e. the body
#    contains "ost. zam. w Kowl..." (ost. zam. = "ostatnio zamieszkały" =
#    "last resided").
# --------------------------------------------------------------------------
KOWEL_RESIDENT_RE = re.compile(r'ost\W{0,4}za\w{1,4}\W{0,3}w\s*Kowl', re.IGNORECASE)


# --------------------------------------------------------------------------
# 5. FIELD EXTRACTORS
# --------------------------------------------------------------------------
def extract_name(body):
    """Name is everything before the first comma."""
    m = re.match(r'([^,]+),', body)
    return m.group(1).strip() if m else ""


# Age: format is ", l. NN," but OCR very often misreads lowercase "l" as
# the digit "1" (and sometimes as "I."), so we accept all three.
AGE_RE = re.compile(r',\s*(?:l|1|I|Ł|ł|L)\.?\s*(\d{1,2})\s*,')

# Birth year: "ur. w 1905 r.", "ur. 5.5.1910 r. w Piotrkowie", or OCR'd
# "urodź, w 1892 r." etc. We just grab the first 4-digit number between
# "ur..." and the next "r.".
BIRTHYEAR_RE = re.compile(r'\bur\w{0,4}\W{0,3}[^,]*?(\d{4})\s*r\.')


def extract_age_or_birth(body):
    m = AGE_RE.search(body)
    if m:
        return m.group(1)
    m = BIRTHYEAR_RE.search(body)
    if m:
        return f"b. {m.group(1)}"
    return ""


# Address: capture whatever follows "ost. zam. w Kowl... przy ul. X"
# up to the next comma. Left AS-IS (declined form) — see module
# docstring limitations.
ADDRESS_RE = re.compile(
    r'ost\W{0,4}za\w{1,4}\W{0,3}w\s*Kowl\w*\s*przy\s*(?:ulicy|ul\.?)\s*([^,]+)',
    re.IGNORECASE,
)


def extract_address(body):
    m = ADDRESS_RE.search(body)
    if m:
        street = m.group(1).strip()
        return f"ul. {street}"
    return ""


# Charge codes: "osk. z art. 51, 440, 448 i 593 k. k." — grab everything
# between "art." and "k. k." then pull out the bare numbers.
CHARGE_RE = re.compile(
    r'osk\W{0,3}z\W{0,3}art\.?\s*([0-9,\s.iI\u2014\u2013vVxX]+?)k\.?\s*k\.?',
    re.IGNORECASE,
)


def extract_charge_codes(body):
    m = CHARGE_RE.search(body)
    if not m:
        return []
    codes_str = m.group(1)
    codes = re.findall(r'\d+', codes_str)
    seen = set()
    out = []
    for c in codes:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


# --------------------------------------------------------------------------
# 6. MAIN PIPELINE
# --------------------------------------------------------------------------
def parse_text(raw):
    cleaned = clean_text(raw)
    entries = split_entries(cleaned)

    rows = []
    warnings = []

    # Every entry normally ends with exactly ONE court-citation date, e.g.
    # "z dn. 25.11.30 r." If a body contains MORE than one, it means the
    # header of a following entry was too garbled for ENTRY_START_RE to
    # recognize, so that next entry's text got silently swallowed into
    # this one's body instead of being split out on its own -- i.e. that
    # next person is currently MISSING from your output entirely.
    CITATION_DATE_RE = re.compile(r'z\s*dni?a?\.?\s*\d{1,2}[.,]\d{1,2}[.,]\d{2}\s*r\.')

    for e in entries:
        body = e["body"]
        n_dates = len(CITATION_DATE_RE.findall(body))
        if n_dates > 1:
            warnings.append(
                f"  Entry #{e['list_no']} (reg. {e['reg_id']}) contains "
                f"{n_dates} court-citation dates instead of 1 -> likely "
                f"swallowed one or more following entries whose header "
                f"the parser couldn't recognize. Check the original text "
                f"right after this entry for a person missing from the CSV."
            )
        if not KOWEL_RESIDENT_RE.search(body):
            continue  # not a Kowel resident -> skip entirely

        name = extract_name(body)
        age = extract_age_or_birth(body)
        address = extract_address(body)
        codes = extract_charge_codes(body)
        charge_codes_str = ", ".join(f"art. {c}" for c in codes) if codes else ""
        charge_english = charge_lookup(codes) if codes else ""

        missing = []
        if not name:
            missing.append("name")
        if not age:
            missing.append("age/birth year")
        if not address:
            missing.append("address")
        if not codes:
            missing.append("charge codes")
        if missing:
            warnings.append(
                f"  Entry #{e['list_no']} (reg. {e['reg_id']}): "
                f"missing {', '.join(missing)} -> check manually"
            )

        rows.append(
            {
                "Name": name,
                "Age / Birth Year": age,
                "Last Known Address in Kowel": address,
                "Penal Code Charge": charge_codes_str,
                "Legal Charge in English": charge_english,
            }
        )

    return rows, warnings


def parse_file(input_path):
    raw = Path(input_path).read_text(encoding="utf-8", errors="replace")
    return parse_text(raw)


def write_csv(rows, output_path):
    fieldnames = [
        "Name",
        "Age / Birth Year",
        "Last Known Address in Kowel",
        "Penal Code Charge",
        "Legal Charge in English",
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    if len(sys.argv) != 3:
        print("Usage: python gazeta_parser.py input.txt output.csv")
        sys.exit(1)

    input_path, output_path = sys.argv[1], sys.argv[2]
    rows, warnings = parse_file(input_path)
    write_csv(rows, output_path)

    print(f"Found {len(rows)} Kowel-resident entries. Wrote {output_path}")
    if warnings:
        print(f"\n{len(warnings)} entries had at least one field that "
              f"couldn't be parsed cleanly (likely OCR noise) — review by hand:")
        for w in warnings:
            print(w)


if __name__ == "__main__":
    main()
