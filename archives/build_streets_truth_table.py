#!/usr/bin/env python3
"""Build archives/normalized/kowel_streets_truth_table.csv from repo sources + OSM."""

from __future__ import annotations

import csv
import json
import re
import unicodedata
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "archives" / "normalized" / "kowel_streets_truth_table.csv"
OSM_CACHE = ROOT / "archives" / "normalized" / "kovel_osm_streets.json"
DOC = ROOT / "archives" / "normalized" / "kowel_streets_truth_table.md"

DIACRITIC_FOLD = str.maketrans(
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
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "h",
        "ґ": "g",
        "д": "d",
        "е": "e",
        "є": "ie",
        "ж": "zh",
        "з": "z",
        "и": "y",
        "і": "i",
        "ї": "i",
        "й": "i",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "kh",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "shch",
        "ь": "",
        "ю": "iu",
        "я": "ia",
        "ы": "y",
        "э": "e",
        "ё": "e",
        "ъ": "",
    }
)

LETTER_ONLY = re.compile(r"^[A-ZŁŻŹĆŃÓĄĘŚ#]$")


def fold(s: str) -> str:
    s = s.strip().lower()
    s = s.translate(DIACRITIC_FOLD)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(
        r"^(ul\.?|ulica|al\.?|aleja|pl\.?|plac|vul\.?|vulytsia|vulytsya|provulok|ploshcha|"
        r"bulvar|вул\.?|улица|площа|провулок|бульвар)\s+",
        "",
        s,
    )
    # Ukrainian names often end with вулиця / провулок
    s = re.sub(r"\s+(vulytsia|vulytsya|provulok|ploshcha|street|alley)$", "", s)
    s = s.replace("’", "'").replace("ʼ", "").replace("`", "'")
    s = re.sub(r"[^a-z0-9\s\-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def clean_display(name: str) -> str:
    name = name.strip().strip(";").strip()
    name = re.sub(r"\s+", " ", name)
    if ";" in name and re.search(r"\.(jpg|png|jpeg)", name, re.I):
        name = name.split(";")[0].strip()
    return name


# Prefer diacritic Polish as display when keys collide
CANONICAL = {
    fold("50 P.P. Strzel. Kres."): "50 P.P. Strzel. Kres.",
    fold("50 P. P, Strzel. Kres."): "50 P.P. Strzel. Kres.",
    fold("50 P. P. Strzel. Kres."): "50 P.P. Strzel. Kres.",
    fold("Łucka"): "Łucka",
    fold("Lucka"): "Łucka",
    fold("Włodzimierska"): "Włodzimierska",
    fold("Włodzmierska"): "Włodzimierska",
    fold("Wlodzimierska"): "Włodzimierska",
    fold("Więzienna"): "Więzienna",
    fold("Wiezienna"): "Więzienna",
    fold("Krótka"): "Krótka",
    fold("Krotka"): "Krótka",
    fold("Długa"): "Długa",
    fold("Dluga"): "Długa",
    fold("Bielińska"): "Bielińska",
    fold("Bielinska"): "Bielińska",
    fold("Budyszczańska"): "Budyszczańska",
    fold("Budyszczanska"): "Budyszczańska",
    fold("Mieszczańska"): "Mieszczańska",
    fold("Mieszczanska"): "Mieszczańska",
    fold("Południowa"): "Południowa",
    fold("Poludniowa"): "Południowa",
    fold("Północna"): "Północna",
    fold("Polnocna"): "Północna",
    fold("Narożna"): "Narożna",
    fold("Narozna"): "Narożna",
    fold("Niecała"): "Niecała",
    fold("Niecala"): "Niecała",
    fold("Wspólna"): "Wspólna",
    fold("Wspolna"): "Wspólna",
    fold("Żórawia"): "Żórawia",
    fold("Zórawia"): "Żórawia",
    fold("Gęsia"): "Gęsia",
    fold("Gesia"): "Gęsia",
    fold("Hoża"): "Hoża",
    fold("Hoza"): "Hoża",
    fold("Myśliwska"): "Myśliwska",
    fold("Myszliwska"): "Myśliwska",
    fold("Ogrodowa"): "Ogrodowa",
    fold("Królowej Bony"): "Królowej Bony",
    fold("Krolowej Bony"): "Królowej Bony",
    fold("ks. Bandurskiego"): "ks. Bandurskiego",
    fold("ks. Bandurskieog"): "ks. Bandurskiego",
    fold("ksiecia Bandurskiego"): "ks. Bandurskiego",
    fold("Legionów"): "Legionów",
    fold("Legionow"): "Legionów",
    fold("Legjonów"): "Legionów",
    fold("Daszyńskiego"): "Daszyńskiego",
    fold("Daszynskiego"): "Daszyńskiego",
    fold("Dąbrowskiego"): "Dąbrowskiego",
    fold("Dabrowskiego"): "Dąbrowskiego",
    fold("Piłsudskiego"): "Piłsudskiego",
    fold("Pilsudskiego"): "Piłsudskiego",
    fold("al. Marszałka Piłsudskiego"): "al. Marszałka Piłsudskiego",
    fold("al. Marszkalwka Pilsudskiego"): "al. Marszałka Piłsudskiego",
    fold("al. Marszkalka Pilsudskiego"): "al. Marszałka Piłsudskiego",
    fold("3 Maja"): "3 Maja",
    fold("3-go Maja"): "3 Maja",
    fold("1-go Maya"): "1-go Maja",
    fold("1-go Maja"): "1-go Maja",
    fold("Szuhajskiego"): "Szuhajskiego",
    fold("Szuchajskiego"): "Szuhajskiego",
    fold("Kołodnicka"): "Kołodnicka",
    fold("Kolodnicka"): "Kołodnicka",
    fold("Nowy Świat"): "Nowy Świat",
    fold("Nowy Swiat"): "Nowy Świat",
    fold("Duża Gonczarna"): "Duża Gonczarna",
    fold("Dużo Gonczarna"): "Duża Gonczarna",
    fold("Mała Gonczarna"): "Mała Gonczarna",
    fold("Mało Gonczarna"): "Mała Gonczarna",
    fold("Pomnikowa"): "Pomnikowa",
    fold("pl. Pomnikowy"): "pl. Pomnikowy",
    fold("Młynarska"): "Młynarska",
    fold("Mlynarska"): "Młynarska",
    fold("Kościelna"): "Kościelna",
    fold("Koscielna"): "Kościelna",
    fold("Kościuszki"): "Kościuszki",
    fold("Kosciuszki"): "Kościuszki",
    fold("Strażacka"): "Strażacka",
    fold("Strazacka"): "Strażacka",
    fold("Żeromskiego"): "Żeromskiego",
    fold("Zeromskiego"): "Żeromskiego",
    fold("Żwirki"): "Żwirki",
    fold("Zwirki"): "Żwirki",
}


def canon(name: str) -> str:
    name = clean_display(name)
    return CANONICAL.get(fold(name), name)


SAME_AS = {
    "Łucka": "corridor:warszawska_lutska",
    "Warszawska": "corridor:warszawska_lutska",
    "Lutske Street": "corridor:warszawska_lutska",
    "Policyjna": "corridor:pomnikowa",
    "Pomnikowa": "corridor:pomnikowa",
    "pl. Pomnikowy": "corridor:pomnikowa",
    "Staro-Kolejowa": "corridor:kolejowa",
    "Nowo-Kolejowa": "corridor:kolejowa",
    "Kolejowa": "corridor:kolejowa",
    "Dworzec Kolejowy": "corridor:kolejowa",
    "Zaułek Kolejowy": "corridor:kolejowa",
    "Old Vakzalna Street": "corridor:kolejowa",
    "Soborny": "corridor:soborna",
    "Soborna": "corridor:soborna",
    "Zaułek Soborny": "corridor:soborna",
    "Duża Gonczarna": "corridor:gonczarna",
    "Mała Gonczarna": "corridor:gonczarna",
    "Obwodowa": "corridor:obwodowa",
    "Okrzei": "corridor:obwodowa",
    "Obwodowa i Okrzei": "corridor:obwodowa",
    "Żwirki": "corridor:zwirki_wigury",
    "Wigury": "corridor:zwirki_wigury",
    "Piłsudskiego": "corridor:pilsudskiego",
    "al. Marszałka Piłsudskiego": "corridor:pilsudskiego",
    "Brzeska": "corridor:brzeska",
    "Monopolowa": "corridor:monopolowa",
    "Kościelna": "corridor:koscielna",
    "Fabryczna": "corridor:fabryczna",
    "Fabritchna Street": "corridor:fabryczna",
    "Szkolna": "corridor:szkolna",
    "Ogrodowa": "corridor:ogrodowa",
    "Piaskowa": "corridor:piaskowa",
    "Strażacka": "corridor:strazacka",
    "Rynek": "corridor:rynek",
    "Kąpielowa": "corridor:kapielowa",
    "Młynarska": "corridor:mlynarska",
    "Górka": "corridor:gorka",
    "Szlachecka": "corridor:szlachecka",
    "Szeroka": "corridor:szeroka",
    "Lubliniecka": "corridor:lubliniecka",
    "Komorowska": "corridor:komorowska",
    "Wola": "corridor:wola",
    "Mickiewicza": "corridor:mickiewicza",
    "Sienkiewicza": "corridor:sienkiewicza",
    "Włodzimierska": "corridor:wlodzimierska",
    "Ludomir Street": "corridor:wlodzimierska",
    "Budyszczańska": "corridor:budyszczanska",
    "Budowlana": "corridor:budowlana",
    "Polna": "corridor:polna",
    "Zielona": "corridor:zielona",
    "Nowa": "corridor:nowa",
    "Parkowa": "corridor:parkowa",
    "Cicha": "corridor:cicha",
    "Topolowa": "corridor:topolowa",
    "Poleska": "corridor:poleska",
    "Północna": "corridor:polnocna",
    "Południowa": "corridor:poludniowa",
    "Rzeczna": "corridor:rzeczna",
    "Nadbrzeżna": "corridor:nadbrzezna",
    "Cerkiewna": "corridor:cerkiewna",
    "Sadowa": "corridor:sadowa",
    "Miodowa": "corridor:miodowa",
    "1-go Maja": "corridor:1maja",
    "Handlowa": "corridor:handlowa",
    "Krótka": "corridor:krotka",
    "Listopadowa": "corridor:listopadowa",
    "Szpitalna": "corridor:szpitalna",
    "Kościuszki": "corridor:kosciuszki",
    "Długa": "corridor:dluga",
    "Maciejowska": "corridor:maciejowska",
}

NOTES = {
    "Łucka": "Renamed ~1919 to Warszawska (street_names.txt); still appears in some 1929–1938 listings",
    "Warszawska": "Formerly Łucka before ~1919; main commercial thoroughfare (today largely вул. Незалежності)",
    "Policyjna": "Earlier name of Pomnikowa (Jaworowski: Policyjna 1 → Pomnikowa 15)",
    "Pomnikowa": "Formerly Policyjna",
    "Staro-Kolejowa": "1920 doctors list; Old Railway Street; related to Kolejowa corridor",
    "Nowo-Kolejowa": "1920 doctors list; New Railway Street; related to Kolejowa corridor",
    "Duża Gonczarna": "Listed as Dużo Gonczarna in some 1938 sources",
    "Mała Gonczarna": "Listed as Mało Gonczarna in some 1938 sources",
    "Obwodowa i Okrzei": "Combined listing in streets.csv; also appears split as Obwodowa / Okrzei",
}

# 1917 occupation Englishized names
OCCUPATION_1917 = {
    "Kaiser Street": ("Kaiser Street (1917)", "corridor:warszawska_lutska", "Occupation-era name; likely Warszawska/Łucka axis"),
    "Brester Street": ("Brester Street (1917)", "corridor:brzeska", "→ Brzeska"),
    "Loizker Street": ("Loizker Street (1917)", "corridor:warszawska_lutska", "→ Łucka / Warszawska"),
    "Monopol Street": ("Monopol Street (1917)", "corridor:monopolowa", "→ Monopolowa"),
    "Holm Street": ("Holm Street (1917)", None, "Chełm direction; mapping uncertain"),
    "Church Street": ("Church Street (1917)", "corridor:koscielna", "→ likely Kościelna"),
    "Factory Street": ("Factory Street (1917)", "corridor:fabryczna", "→ Fabryczna"),
    "School Street": ("School Street (1917)", "corridor:szkolna", "→ Szkolna"),
    "Garden Street": ("Garden Street (1917)", "corridor:ogrodowa", "→ Ogrodowa"),
    "Sand Street": ("Sand Street (1917)", "corridor:piaskowa", "→ Piaskowa"),
    "Fire Street": ("Fire Street (1917)", "corridor:strazacka", "→ Strażacka"),
    "Bridge Street": ("Bridge Street (1917)", None, "Mapping uncertain"),
    "Market Street": ("Market Street (1917)", "corridor:rynek", "→ Rynek area"),
    "Bath Street": ("Bath Street (1917)", "corridor:kapielowa", "→ Kąpielowa"),
    "Memorial Street": ("Memorial Street (1917)", "corridor:pomnikowa", "→ Pomnikowa / Policyjna"),
    "Cross Street": ("Cross Street (1917)", None, "Mapping uncertain"),
    "Miller Street": ("Miller Street (1917)", "corridor:mlynarska", "→ Młynarska"),
    "Jewish Street": ("Jewish Street (1917)", None, "Jewish quarter; mapping uncertain"),
    "Gymnasium Street": ("Gymnasium Street (1917)", "corridor:szkolna", "Near schools / Szkolna"),
    "Garka Street": ("Garka Street (1917)", "corridor:gorka", "→ Górka"),
    "Hantsharne Street": ("Hantsharne Street (1917)", "corridor:gonczarna", "→ Gonczarna"),
    "Sliachetske Street": ("Sliachetske Street (1917)", "corridor:szlachecka", "→ Szlachecka"),
    "Broad Street": ("Broad Street (1917)", "corridor:szeroka", "→ Szeroka"),
    "Lublin Street": ("Lublin Street (1917)", "corridor:lubliniecka", "→ Lubliniecka"),
    "Kamarawer Street": ("Kamarawer Street (1917)", "corridor:komorowska", "→ Komorowska"),
    "Turkish Street": ("Turkish Street (1917)", None, "Mapping uncertain"),
    "Canal Street": ("Canal Street (1917)", None, "Mapping uncertain"),
    "Landwehr Street": ("Landwehr Street (1917)", None, "Occupation military name"),
    "Landwehr-Canal Street": ("Landwehr-Canal Street (1917)", None, "Occupation military name"),
    "Landwehr Canal Street": ("Landwehr Canal Street (1917)", None, "Occupation military name"),
    "Bavaria Street": ("Bavaria Street (1917)", None, "Occupation name"),
    "Prussian Street": ("Prussian Street (1917)", None, "Occupation name"),
    "Nikolayev Street": ("Nikolayev Street (1917)", None, "Occupation / Russian-era name"),
    "Franz Josef Street": ("Franz Josef Street (1917)", None, "Occupation name"),
    "Friedrich Wilhelm Street": ("Friedrich Wilhelm Street (1917)", None, "Occupation name"),
    "King Ferdinand Street": ("King Ferdinand Street (1917)", None, "Occupation name"),
    "Luitpold Street": ("Luitpold Street (1917)", None, "Occupation name"),
    "Artillery Street": ("Artillery Street (1917)", None, "Occupation name"),
    "Infantry Street": ("Infantry Street (1917)", None, "Occupation name"),
    "Command Street": ("Command Street (1917)", None, "Occupation name"),
    "Judge Street": ("Judge Street (1917)", None, "Occupation name"),
    "Jurist Street": ("Jurist Street (1917)", None, "Occupation name"),
    "Magazine Street": ("Magazine Street (1917)", None, "Occupation name"),
    "Star Street": ("Star Street (1917)", None, "Occupation name"),
    "Privislian Street": ("Privislian Street (1917)", None, "Occupation name"),
    "Badghaw Street": ("Badghaw Street (1917)", None, "Occupation name; OCR uncertain"),
    "Hagwer Street": ("Hagwer Street (1917)", None, "Occupation name; OCR uncertain"),
    "Dingerflain (Wallia)": ("Dingerflain / Wallia (1917)", "corridor:wola", "Possibly Wola"),
    "Suarawer Street": ("Suarawer Street (1917)", None, "Occupation name; OCR uncertain"),
    "Halter Street": ("Halter Street (1917)", None, "Occupation name"),
    "Karl Street": ("Karl Street (1917)", None, "Occupation name"),
    "Kowel II": ("Kowel II (1917)", None, "District/area label, not a street"),
}

# OSM cognate tokens (folded Latin) that confirm a corridor still exists
CORRIDOR_OSM_HINTS = {
    "corridor:warszawska_lutska": ["nezalezhnosti", "varshavska", "lutska"],
    "corridor:brzeska": ["brestska"],
    "corridor:kolejowa": ["zaliznychna", "shevchenka", "vokzal"],
    "corridor:monopolowa": ["monopol"],
    "corridor:koscielna": ["kostel", "tserkovna"],
    "corridor:fabryczna": ["fabrychna", "zavodska"],
    "corridor:szkolna": ["shkilna"],
    "corridor:ogrodowa": ["sadova", "ohorod"],
    "corridor:piaskowa": ["pishchana"],
    "corridor:strazacka": ["pozhezh"],
    "corridor:rynek": ["rynok", "heroiv maidanu", "teatralna", "tsentralna"],
    "corridor:kapielowa": [],
    "corridor:mlynarska": [],
    "corridor:gorka": [],
    "corridor:gonczarna": ["honcharna", "goncharna"],
    "corridor:szlachecka": [],
    "corridor:szeroka": [],
    "corridor:lubliniecka": [],
    "corridor:komorowska": [],
    "corridor:wola": ["voli", "woli"],
    "corridor:pomnikowa": [],
    "corridor:soborna": ["soborna"],
    "corridor:obwodowa": ["okruzhna", "kiltsova"],
    "corridor:zwirki_wigury": [],
    "corridor:pilsudskiego": [],
    "corridor:mickiewicza": ["mitskevycha", "mickiewicz"],
    "corridor:sienkiewicza": ["senkevycha"],
    "corridor:wlodzimierska": ["volodymyrska"],
    "corridor:budyszczanska": ["budyshchanska"],
    "corridor:budowlana": ["budivelna"],
    "corridor:polna": ["polova"],
    "corridor:zielona": ["zelena"],
    "corridor:nowa": ["nova"],
    "corridor:parkowa": ["parkova"],
    "corridor:cicha": ["tykha", "tykhyi"],
    "corridor:topolowa": ["topoleva", "topolina"],
    "corridor:poleska": ["poliska"],
    "corridor:polnocna": ["pivnichna"],
    "corridor:poludniowa": ["pivdenna"],
    "corridor:rzeczna": ["richkova"],
    "corridor:nadbrzezna": ["naberezhna"],
    "corridor:cerkiewna": ["tserkovna"],
    "corridor:sadowa": ["sadova"],
    "corridor:miodowa": ["medova"],
    "corridor:1maja": ["1 travnia", "travneva"],
    "corridor:handlowa": ["torhova", "poshtova"],
    "corridor:krotka": ["korotka"],
    "corridor:listopadowa": ["lystopadova"],
    "corridor:szpitalna": ["chervonoho khresta", "likarn"],
    "corridor:kosciuszki": ["kostiuszka", "kostyushka"],
    "corridor:dluga": ["dovha"],
    "corridor:maciejowska": [],
}

# Direct Polish name → OSM hint tokens
NAME_OSM_HINTS = {
    fold("Warszawska"): ["nezalezhnosti", "varshavska"],
    fold("Łucka"): ["lutska", "nezalezhnosti"],
    fold("Brzeska"): ["brestska"],
    fold("Kolejowa"): ["zaliznychna", "shevchenka"],
    fold("Mickiewicza"): ["mitskevycha"],
    fold("Sienkiewicza"): ["senkevycha"],
    fold("Włodzimierska"): ["volodymyrska"],
    fold("Fabryczna"): ["fabrychna"],
    fold("Szkolna"): ["shkilna"],
    fold("Piaskowa"): ["pishchana"],
    fold("Budyszczańska"): ["budyshchanska"],
    fold("Budowlana"): ["budivelna"],
    fold("Soborna"): ["soborna"],
    fold("Duża Gonczarna"): ["velyka honcharna", "honcharna"],
    fold("Mała Gonczarna"): ["mala honcharna", "honcharna"],
    fold("Polna"): ["polova"],
    fold("Zielona"): ["zelena"],
    fold("Nowa"): ["nova"],
    fold("Parkowa"): ["parkova"],
    fold("Cicha"): ["tykha"],
    fold("Topolowa"): ["topoleva"],
    fold("Poleska"): ["poliska"],
    fold("Północna"): ["pivnichna"],
    fold("Południowa"): ["pivdenna"],
    fold("Rzeczna"): ["richkova"],
    fold("Nadbrzeżna"): ["naberezhna"],
    fold("Cerkiewna"): ["tserkovna"],
    fold("Sadowa"): ["sadova"],
    fold("Miodowa"): ["medova"],
    fold("1-go Maja"): ["1 travnia", "travneva"],
    fold("Ogrodowa"): ["sadova"],
    fold("Obwodowa"): ["okruzhna", "kiltsova"],
    fold("Wola"): ["voli"],
    fold("Kościuszki"): ["kostiush"],
    fold("Szpitalna"): ["chervonoho khresta"],
    fold("Kopernika"): ["kopernyka"],
    fold("Szewczenki"): ["shevchenka"],
}


def prefer_display(existing: str, new: str) -> str:
    """Keep better display name when fold keys collide."""
    key = fold(new) or fold(existing)
    if key in CANONICAL:
        return CANONICAL[key]
    if not existing:
        return new
    if not new:
        return existing
    # Prefer form without pl./ul. prefix when both fold to same key via strip
    ex_pl = bool(re.match(r"^(pl\.|ul\.|al\.)\s+", existing, re.I))
    new_pl = bool(re.match(r"^(pl\.|ul\.|al\.)\s+", new, re.I))
    if ex_pl and not new_pl:
        return new
    if new_pl and not ex_pl:
        return existing
    return existing if len(existing) >= len(new) else new


def add_attest(store, name: str, year: int, source: str, *, allow_new: bool = True):
    name = name.strip()
    if not name or LETTER_ONLY.match(name):
        return
    if name in {"#", "REFERENCE", "X", "Y", "Z", "E", "F", "I", "J", "N", "O", "P", "R", "S", "T", "U", "V", "W"}:
        return
    low = name.lower()
    if low in {"starostwo", "szpital powiatowy", "szpital epidemiczny"} or low.startswith("szpital "):
        return
    if re.search(r"\(\s*<?\d{4}", name) and "/" in name:
        for part in name.split("/"):
            base = re.sub(r"\(.*?\)", "", part).strip()
            if base:
                add_attest(store, base, year, source, allow_new=allow_new)
        return

    display = canon(name)
    key = fold(display)
    if not key:
        return
    if not allow_new and key not in store:
        # try fuzzy: match if folded name equals an existing key
        return
    entry = store[key]
    entry["street_name"] = prefer_display(entry.get("street_name", ""), display)
    entry["years"].add(year)
    entry["sources"].add(source)


def load_streets_csv(store):
    with (ROOT / "streets.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            add_attest(store, row["name"], 1938, "streets_csv")


def load_street_names_txt(store):
    for line in (ROOT / "street_names.txt").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("Partial") or line.startswith("Sources") or line == "#":
            continue
        if LETTER_ONLY.match(line):
            continue
        base = line.split(";")[0].strip()
        if not base:
            continue
        if "Łucka" in base and "Warszawska" in base and "/" in base:
            add_attest(store, "Łucka", 1919, "street_names_txt")
            add_attest(store, "Warszawska", 1919, "street_names_txt")
            continue
        add_attest(store, base, 1929, "street_names_txt")
        add_attest(store, base, 1938, "street_names_txt")


def load_voting(store):
    voting = ROOT / "archives" / "landmark_map_gold_standard" / "voting_districts_kowel.csv"
    legacy = ROOT / "kowel_voting_districts.csv"
    path = voting if voting.exists() else legacy
    with path.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            raw = (
                row.get("street")
                or row.get("Miescowosci (ulice) wchodzace w sklad obwodu")
                or ""
            ).strip()
            if not raw:
                continue
            raw = re.sub(r"^(ul\.?|ulica)\s+", "", raw, flags=re.I)
            # Keep only the street token before range notes
            raw = re.split(r"\s+od\s+", raw, maxsplit=1)[0]
            raw = re.split(r"\s+do\s+", raw, maxsplit=1)[0]
            raw = raw.strip(" ,")
            # Drop leftover garbage like "Magistrackiej lewa strona"
            if "lewa strona" in raw.lower() or "prawa strona" in raw.lower():
                continue
            if not raw:
                continue
            add_attest(store, raw, 1938, "voting_1938")


def extract_street_from_address(addr: str) -> str | None:
    if not addr or not str(addr).strip():
        return None
    addr = str(addr).strip()
    m = re.match(r"^(.*?)(?:\s+\d+[A-Za-z]?(?:/[A-Za-z0-9]+)?(?:\s*M)?\s*)?$", addr)
    street = (m.group(1) if m else addr).strip(" ,.")
    street = re.sub(r"^(ul\.?|ulica)\s+", "", street, flags=re.I)
    if not street or street.isdigit() or len(fold(street)) < 3:
        return None
    return street


def load_directory_attest_only(store):
    """Attest years for streets already seeded; do not invent OCR junk rows."""
    p = ROOT / "streets_by_business_address_count.csv"
    with p.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            add_attest(store, row["Street"], 1929, "directory_1929_counts", allow_new=False)

    p = ROOT / "1929_business_directory.csv"
    with p.open(encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            street = extract_street_from_address(row.get("Address") or "")
            if street:
                add_attest(store, street, 1929, "directory_1929", allow_new=False)


def load_residents(store):
    for label, path in [
        ("residents_1938", ROOT / "kowel_residents_1938.csv"),
        ("normalized_directory", ROOT / "archives" / "normalized_directory_kowel.csv"),
    ]:
        if not path.exists():
            continue
        with path.open(encoding="utf-8", errors="replace") as f:
            for row in csv.DictReader(f):
                street = (row.get("Street") or "").strip()
                if street:
                    add_attest(store, street, 1938, label, allow_new=False)


def load_doctors(store):
    with (ROOT / "doctors_resident_in_kowel.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            street = (row.get("street") or "").strip()
            if street:
                add_attest(store, street, 1920, "doctors_1920", allow_new=True)


def load_grain(store):
    with (ROOT / "archives" / "ww1_grain_distribution_kowel.csv").open(encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            for token in row[2:]:
                token = token.strip()
                if not token:
                    continue
                if token in OCCUPATION_1917:
                    disp, corridor, note = OCCUPATION_1917[token]
                else:
                    disp = f"{token} (1917)"
                    corridor, note = None, "occupation_1917_unmapped"
                key = fold(disp)
                entry = store[key]
                entry["street_name"] = disp
                entry["years"].add(1917)
                entry["sources"].add("grain_1917")
                if corridor:
                    entry["same_as"] = corridor
                entry["notes"] = note


def load_aliases(store):
    aliases = [
        ("Lutske Street", 1929, "yizkor_buildings", "corridor:warszawska_lutska", "Yiddish/Hebrew form of Łucka"),
        ("Ludomir Street", 1929, "yizkor_buildings", "corridor:wlodzimierska", "Yiddish form related to Włodzimierska / Ludmir"),
        ("Fabritchna Street", 1929, "yizkor_buildings", "corridor:fabryczna", "Yiddish form of Fabryczna"),
        ("Matseyev Street", 1929, "yizkor_buildings", None, "Yiddish form (Matseyever)"),
        ("Old Vakzalna Street", 1929, "places_described", "corridor:kolejowa", "Old station street"),
        ("Shinena", 1929, "hebrew_map", None, "Synagogue Street (Hebrew map label)"),
        ("Zaułek Soborny", 1929, "directory_1929", "corridor:soborna", "Alley off Soborna"),
    ]
    for name, year, src, corridor, note in aliases:
        key = fold(name)
        entry = store[key]
        entry["street_name"] = name
        entry["years"].add(year)
        entry["sources"].add(src)
        if corridor:
            entry["same_as"] = corridor
        entry["notes"] = note


def fetch_osm_names() -> list[str]:
    if OSM_CACHE.exists():
        return json.loads(OSM_CACHE.read_text(encoding="utf-8"))
    query = (
        '[out:json][timeout:90];'
        'way["highway"]["name"](51.18,24.66,51.25,24.78);'
        "out tags;"
    )
    req = urllib.request.Request(
        "https://overpass-api.de/api/interpreter",
        data=query.encode("utf-8"),
        headers={"User-Agent": "kowel-streets-truth-table/1.0"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.load(resp)
    names = sorted({e["tags"]["name"] for e in data["elements"] if "name" in e.get("tags", {})})
    OSM_CACHE.write_text(json.dumps(names, ensure_ascii=False, indent=2), encoding="utf-8")
    return names


def hints_match(hints: list[str], osm_folds: list[str]) -> bool:
    for h in hints:
        hf = fold(h)
        if not hf:
            continue
        for o in osm_folds:
            if hf == o or hf in o or (len(hf) >= 5 and o in hf):
                return True
    return False


def decide_exists(street_name: str, same_as: str | None, osm_folds: list[str], osm_raw: list[str]) -> tuple[str, str]:
    """Return (y/n, optional note suffix)."""
    key = fold(street_name)
    occ_note = "exists_today refers to physical corridor, not occupation name"

    # Non-street / ephemeral labels
    if key in {"tranzyt sarny", "tranzyt lubelski", "kowel ii (1917)"}:
        return "n", "Route/area label rather than a lasting street corridor"

    # Occupation label with no corridor link: the name itself does not survive
    if street_name.endswith("(1917)") and not same_as:
        return "n", "occupation_1917_unmapped"

    if same_as and hints_match(CORRIDOR_OSM_HINTS.get(same_as, []), osm_folds):
        return "y", occ_note if street_name.endswith("(1917)") else ""

    if hints_match(NAME_OSM_HINTS.get(fold(street_name), []), osm_folds):
        return "y", ""

    # Direct fold equality against OSM
    if key and key in set(osm_folds):
        return "y", ""

    # Mapped occupation / alias rows inherit corridor presumption
    if same_as:
        note = occ_note if street_name.endswith("(1917)") else "corridor presumed from continuous urban fabric; no direct OSM name match"
        return "y", note

    # Unmapped occupation names (defensive)
    if street_name.endswith("(1917)"):
        return "n", "occupation_1917_unmapped"

    return "y", "corridor presumed from continuous urban fabric; no direct OSM name match"


def load_landmark_status() -> dict[str, str]:
    """fold(name) -> existing|modified|destroyed|..."""
    out = {}
    path = ROOT / "maps" / "kowel_landmarks_index.csv"
    if not path.exists():
        return out
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            desc = row.get("Description") or ""
            polish = row.get("Polish") or ""
            status = (row.get("Status") or "").strip().lower()
            for label in (desc, polish):
                if "street" in label.lower() or label.lower().startswith("ulica"):
                    out[fold(label)] = status
    return out


def build():
    store: dict[str, dict] = defaultdict(
        lambda: {"street_name": "", "years": set(), "sources": set(), "same_as": None, "notes": ""}
    )

    # Seed from authoritative lists first
    load_streets_csv(store)
    load_street_names_txt(store)
    load_voting(store)
    load_doctors(store)
    # Attest-only layers
    load_directory_attest_only(store)
    load_residents(store)
    load_grain(store)
    load_aliases(store)

    for key, entry in store.items():
        name = entry["street_name"]
        if name in SAME_AS and not entry.get("same_as"):
            entry["same_as"] = SAME_AS[name]
        if name in NOTES and not entry.get("notes"):
            entry["notes"] = NOTES[name]

    print("Loading OSM street names…")
    osm_names = fetch_osm_names()
    print(f"  {len(osm_names)} named highways in bbox")
    osm_folds = [fold(n) for n in osm_names]
    landmarks = load_landmark_status()

    rows = []
    for key, entry in store.items():
        name = entry["street_name"]
        if not name:
            continue
        years = ";".join(str(y) for y in sorted(entry["years"]))
        sources = ";".join(sorted(entry["sources"]))
        same_as = entry.get("same_as") or SAME_AS.get(name, "")
        notes = entry.get("notes") or NOTES.get(name, "")

        exists, extra = decide_exists(name, same_as or None, osm_folds, osm_names)
        # landmark override
        st = landmarks.get(fold(name), "")
        if st in {"destroyed"} and not same_as:
            exists = "n"
            extra = (extra + "; " if extra else "") + "landmark Status=destroyed"
        elif st in {"existing", "modified", "standing"} and exists != "y":
            exists = "y"
            extra = (extra + "; " if extra else "") + f"landmark Status={st}"

        if same_as and hints_match(CORRIDOR_OSM_HINTS.get(same_as, []), osm_folds):
            exists = "y"

        if extra:
            notes = f"{notes}; {extra}" if notes else extra

        # Drop the weak default note when we have a strong OSM hit
        if exists == "y" and "no direct OSM name match" in notes and hints_match(
            CORRIDOR_OSM_HINTS.get(same_as, []) + NAME_OSM_HINTS.get(fold(name), []), osm_folds
        ):
            notes = notes.replace("; corridor presumed from continuous urban fabric; no direct OSM name match", "")
            notes = notes.replace("corridor presumed from continuous urban fabric; no direct OSM name match", "")
            notes = notes.strip("; ").strip()

        rows.append(
            {
                "street_name": name,
                "year_ranges": years,
                "exists_today": exists,
                "same_as": same_as,
                "notes": notes,
                "sources": sources,
            }
        )

    rows.sort(key=lambda r: (fold(r["street_name"]), r["street_name"]))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["street_name", "year_ranges", "exists_today", "same_as", "notes", "sources"],
        )
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote {len(rows)} rows → {OUT}")
    from collections import Counter

    print("exists_today", Counter(r["exists_today"] for r in rows))
    for must in ["Łucka", "Warszawska", "Policyjna", "Pomnikowa", "Staro-Kolejowa", "Kolejowa", "Duża Gonczarna"]:
        hit = next((r for r in rows if r["street_name"] == must), None)
        print(f"  QA {must}: {hit['year_ranges'] if hit else 'MISSING'} exists={hit['exists_today'] if hit else '-'}")

    # coverage vs streets.csv
    streets = {canon(r["name"]) for r in csv.DictReader((ROOT / "streets.csv").open(encoding="utf-8"))}
    out_names = {r["street_name"] for r in rows}
    missing = sorted(streets - out_names, key=fold)
    # account for Obwodowa i Okrzei split
    missing = [m for m in missing if m not in {"Obwodowa i Okrzei"} or ("Obwodowa" not in out_names)]
    print(f"streets.csv names missing from truth table: {len(missing)}")
    if missing[:15]:
        print("  sample:", missing[:15])

    DOC.write_text(
        "\n".join(
            [
                "# Kowel streets truth table",
                "",
                f"File: `{OUT.relative_to(ROOT).as_posix()}`",
                "",
                "## Columns",
                "",
                "- `street_name` — one historical name form per row (Polish preferred)",
                "- `year_ranges` — attestation years from repo sources (`1917;1929;1938`)",
                "- `exists_today` — `y`/`n` if the **physical corridor** still appears on a modern map of Kovel",
                "- `same_as` — shared corridor id linking renames/aliases",
                "- `notes` — rename / matching notes",
                "- `sources` — local datasets that attested the name",
                "",
                "## How it was built",
                "",
                "1. Seed names from `streets.csv`, `street_names.txt`, `archives/landmark_map_gold_standard/voting_districts_kowel.csv`, `doctors_resident_in_kowel.csv`.",
                "2. Add attestation years from 1929 directories and 1938 phone/normalized listings (match-only; OCR junk not added as new streets).",
                "3. Add 1917 occupation names from `archives/ww1_grain_distribution_kowel.csv` and selected Yiddish/Hebrew aliases.",
                "4. Set `exists_today` using OpenStreetMap named highways in bbox 51.18–51.25N, 24.66–24.78E (see `kovel_osm_streets.json`), Polish→Ukrainian cognate hints, and landmark status when available.",
                "",
                "## Limits",
                "",
                "- Attestation years ≠ full official rename gazetteer.",
                "- Many interwar streets survive under different Ukrainian names; where no cognate match was found, `exists_today=y` is a corridor presumption for the continuous urban fabric (see notes).",
                "- Unmapped 1917 occupation labels are `exists_today=n` for the label itself.",
                "",
                f"Regenerate: `python archives/build_streets_truth_table.py`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"Wrote {DOC}")


if __name__ == "__main__":
    build()
