"""WHO Disease Outbreak News (DON): the outbreak notices WHO publishes, from its public API (no key).

    https://www.who.int/api/news/diseaseoutbreaknews  (OData; $top is capped at 100)

Kept per notice: WHO's id, title, the disease and place read from the title, the countries and WHO regions in the
place, the publication date and the link. WHO's terms allow extracts for research with acknowledgement, not
reproduction of substantial portions, so no body text (summary, assessment, advice) is kept or published.
Two pages (200 notices, about four years) are read: the last PUBLISH_DAYS are published, the rest give each
country's own record.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from . import places

API = "https://www.who.int/api/news/diseaseoutbreaknews"
PAGE_URL = API + "?$top=100&$skip={skip}&$orderby=PublicationDateAndTime%20desc"
PAGES = 2
ITEM_PAGE = "https://www.who.int/emergencies/disease-outbreak-news/item/{slug}"
PUBLISH_DAYS = 365
LOOKBACK_DAYS = 730


def parse_page(body: bytes) -> list[dict]:
    doc = json.loads(body.decode("utf-8"))
    if not isinstance(doc, dict) or not isinstance(doc.get("value"), list):
        raise ValueError("WHO DON reply has no value list")
    return doc["value"]


def record(v: dict) -> dict:
    title = (v.get("Title") or v.get("OverrideTitle") or "").replace("�", "–").strip()
    disease, place = places.split_title(title)
    ccs, regions, rest = places.countries_in(place or "")
    shown = v.get("PublicationDateAndTime") or v.get("PublicationDate")
    slug = v.get("UrlName") or (v.get("ItemDefaultUrl") or "").strip("/")
    return {
        "key": f"who:{v.get('DonId') or v.get('Id')}",
        "lane": "who",
        "don_id": v.get("DonId"),
        "title": title,
        "disease": disease,
        "place": place,
        "countries": ccs,
        "regions": regions,
        # Parsed when the title has a place and something in it was recognised; a title with no place
        # ("Avian Influenza A(H9N2)") is not a parse failure.
        "place_parsed": (not place) or bool(ccs or regions),
        "place_unread": rest if place and not (ccs or regions) else None,
        "published_day": shown[:10] if shown else None,
        "published_at_api": v.get("PublicationDate"),
        "last_modified": v.get("LastModified"),
        "url": ITEM_PAGE.format(slug=slug),
    }


def all_records(values: list[dict]) -> list[dict]:
    """Every notice read, de-duplicated on id, with no age cut (the retention archive keeps them all)."""
    seen, out = set(), []
    for v in values:
        if not (v.get("DonId") or v.get("Id")):
            continue
        r = record(v)
        if r["key"] not in seen:
            seen.add(r["key"])
            out.append(r)
    return sorted(out, key=lambda r: r["key"])


def build(values: list[dict], today: date) -> tuple[list[dict], dict]:
    recs = [record(v) for v in values if v.get("DonId") or v.get("Id")]
    seen, uniq = set(), []
    for r in recs:
        if r["key"] in seen:
            continue
        seen.add(r["key"])
        uniq.append(r)
    uniq.sort(key=lambda r: (r["published_day"] or "", r["key"]), reverse=True)
    oldest = min((r["published_day"] for r in uniq if r["published_day"]), default=None)
    cutoff = (today - timedelta(days=PUBLISH_DAYS)).isoformat()
    out = []
    for r in uniq:
        if not r["published_day"] or r["published_day"] < cutoff:
            continue
        d = date.fromisoformat(r["published_day"])
        lb = (d - timedelta(days=LOOKBACK_DAYS)).isoformat()
        prior = {}
        for cc in r["countries"]:
            prior[cc] = sum(1 for o in uniq if o is not r and cc in o["countries"]
                            and o["published_day"] and lb <= o["published_day"] < r["published_day"])
        r = dict(r)
        # Only meaningful when the read reaches back the whole look-back window.
        r["prior_notices_730_days"] = prior if oldest and oldest <= lb else None
        out.append(r)
    parsed = [r for r in out if r["place"]]
    extra = {"read": len(uniq), "published": len(out), "oldest_read": oldest,
             "places_parsed": sum(1 for r in parsed if r["place_parsed"]), "places_stated": len(parsed),
             "unread_places": [r["place"] for r in parsed if not r["place_parsed"]]}
    return out, extra


def day_utc(d: str) -> str:
    return datetime.fromisoformat(d).strftime("%Y-%m-%dT00:00:00Z")
