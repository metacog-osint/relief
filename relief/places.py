"""Country names to ISO 3166-1 alpha-2, for WHO Disease Outbreak News titles.

WHO titles put the place after the disease, in WHO's own country names ("the Plurinational State of Bolivia",
"Iran (Islamic Republic of)", "United Republic of Tanzania"). The kit's names (Natural Earth) are matched first,
then WHO's forms below. Matching is longest name first, on word boundaries, and each match removes its span, so
"Niger" never matches inside "Nigeria" and "Sudan" never inside "South Sudan". Only the place part of a title is
read, never the disease part ("Sudan virus disease", "Marburg virus disease").
"""
from __future__ import annotations

import re
import sys
import unicodedata
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "doctrine" / "kit" / "python"))
from tic_doctrine import geo  # noqa: E402

# WHO's and IFRC's own forms, and common short forms. Keys are normalised by norm().
ALIASES = {
    "the russian federation": "RU", "russian federation": "RU", "russia": "RU",
    "kingdom of saudi arabia": "SA", "saudi arabia": "SA",
    "united republic of tanzania": "TZ", "tanzania": "TZ", "tanzania, united republic of": "TZ",
    "the plurinational state of bolivia": "BO", "plurinational state of bolivia": "BO",
    "bolivia (plurinational state of)": "BO", "bolivia": "BO",
    "iran (islamic republic of)": "IR", "islamic republic of iran": "IR", "iran": "IR",
    "united states of america": "US", "united states": "US", "usa": "US",
    "united kingdom of great britain and northern ireland": "GB", "united kingdom": "GB",
    "democratic republic of the congo": "CD", "drc": "CD", "congo, democratic republic of the": "CD",
    "republic of the congo": "CG", "congo": "CG",
    "turkiye": "TR", "turkey": "TR",
    "viet nam": "VN", "vietnam": "VN",
    "lao people's democratic republic": "LA", "laos": "LA",
    "republic of korea": "KR", "south korea": "KR",
    "democratic people's republic of korea": "KP", "north korea": "KP",
    "syrian arab republic": "SY", "syria": "SY",
    "occupied palestinian territory": "PS", "occupied palestinian territory, including east jerusalem": "PS",
    "palestine": "PS",
    "cote d'ivoire": "CI", "ivory coast": "CI",
    "cabo verde": "CV", "cape verde": "CV",
    "venezuela (bolivarian republic of)": "VE", "bolivarian republic of venezuela": "VE", "venezuela": "VE",
    "the netherlands": "NL", "netherlands": "NL", "kingdom of the netherlands": "NL",
    "republic of moldova": "MD", "moldova": "MD",
    "state of qatar": "QA", "the state of qatar": "QA",
    "the gambia": "GM", "gambia": "GM",
    "eswatini": "SZ", "swaziland": "SZ",
    "czechia": "CZ", "czech republic": "CZ",
    "north macedonia": "MK",
    "micronesia (federated states of)": "FM",
    "brunei darussalam": "BN",
    "timor-leste": "TL", "east timor": "TL",
    "myanmar": "MM", "burma": "MM",
    "kyrgyzstan": "KG", "kyrgyz republic": "KG",
    "hong kong sar": "HK", "china, hong kong sar": "HK", "hong kong": "HK",
    "taiwan": "TW",
    "kosovo": "XK",
    # French overseas departments, which WHO names on their own. The kit has no label point for them, so
    # TERRITORY_POINTS below gives one (each department's prefecture, rounded).
    "la reunion": "RE", "reunion": "RE", "mayotte": "YT", "guadeloupe": "GP", "martinique": "MQ",
    "french guiana": "GF",
}

# [lat, lon] for places the kit's points.json leaves out.
TERRITORY_POINTS = {"RE": [-20.88, 55.45], "YT": [-12.78, 45.23], "GP": [16.24, -61.53], "MQ": [14.61, -61.07],
                    "GF": [4.94, -52.33]}


def point(cc: str):
    """[lat, lon] label point for a code: the kit's, else TERRITORY_POINTS, else None."""
    return geo.point(cc) or TERRITORY_POINTS.get(str(cc or "").upper())

# WHO regions and multi-country wording: a place, but no country. Kept as `regions` on the item.
REGIONS = [
    ("african region", "WHO African Region"), ("afro", "WHO African Region"),
    ("region of the americas", "WHO Region of the Americas"), ("americas", "WHO Region of the Americas"),
    ("eastern mediterranean region", "WHO Eastern Mediterranean Region"),
    ("european region", "WHO European Region"),
    ("south-east asia region", "WHO South-East Asia Region"),
    ("western pacific region", "WHO Western Pacific Region"),
    ("northern hemisphere", "Northern Hemisphere"),
    ("east, west and central africa region", "East, West and Central Africa"),
    ("multi-country", "Multi-country"), ("multi-locations", "Multi-country"), ("multi-region", "Multi-country"),
    ("global situation", "Global"), ("global", "Global"),
]


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", s).strip().lower()


@cache
def _table() -> list[tuple[str, str]]:
    out = {}
    for cc, name in geo._names().items():  # noqa: SLF001 (the kit exposes no public list)
        out[norm(name)] = cc
    out.update({norm(k): v for k, v in ALIASES.items()})
    return sorted(out.items(), key=lambda kv: -len(kv[0]))


def countries_in(text: str) -> tuple[list[str], list[str], str]:
    """(country codes in order of appearance, region labels, leftover text) for a place phrase."""
    t = norm(text)
    found: list[tuple[int, str]] = []
    for name, cc in _table():
        for m in re.finditer(r"(?<![\w-])" + re.escape(name) + r"(?![\w-])", t):
            found.append((m.start(), cc))
            t = t[:m.start()] + " " * (m.end() - m.start()) + t[m.end():]
    regions: list[str] = []
    for phrase, label in REGIONS:
        for m in re.finditer(r"(?<![\w-])" + re.escape(phrase) + r"(?![\w-])", t):
            if label not in regions:
                regions.append(label)
            t = t[:m.start()] + " " * (m.end() - m.start()) + t[m.end():]
    ccs = list(dict.fromkeys(cc for _, cc in sorted(found)))
    rest = re.sub(r"\b(and|the|republic of|state of|kingdom of|with a focus on|countries experiencing current surges"
                  r"|in)\b", " ", t)
    rest = re.sub(r"[\s,&()\-–—]+", " ", rest).strip()
    return ccs, regions, rest


# A title is "<disease> <separator> <place>". The separator is a dash with a space on at least one side, a dash
# straight after a closing bracket ("A(H5N2)-Mexico"), an en or em dash between a word and a capital
# ("Disease–United Republic of Tanzania"), or failing those the first comma. "COVID-19" has a hyphen with
# no space, so it is never split.
SEP = re.compile(r"\s+[-–—]\s*|[-–—]\s+|(?<=\))[-–—](?=[A-Z])"
                 r"|(?<=[a-z])[–—](?=[A-Z])")


def split_title(title: str) -> tuple[str, str | None]:
    title = re.sub(r"\s+", " ", (title or "").replace("�", "–")).strip()
    m = SEP.search(title)
    if m:
        return title[:m.start()].strip(" ,"), title[m.end():].strip(" ,") or None
    if "," in title:
        head, tail = title.split(",", 1)
        return head.strip(), tail.strip() or None
    return title, None
