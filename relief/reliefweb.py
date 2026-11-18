"""ReliefWeb (OCHA): the disasters ReliefWeb currently tracks, and how many reports it has posted on each disaster
and each country in the last 7 days against the 12 weeks before.

Read from the ReliefWeb API (api.reliefweb.int/v2), three calls a run (ReliefWeb allows 1,000 a day and 1,000
entries a call). Every call needs ReliefWeb's pre-approved appname as a query parameter: it is read from
RELIEFWEB_APPNAME, added to the URL only when the request is made, and never recorded, logged or published (the
raw index and the snapshot keep the URL without it).

Terms (reliefweb.int/terms-conditions, read 18 Nov 2026): personal, non-commercial use, with no right to
redistribute, compile or create derivative works from ReliefWeb's materials. So Relief publishes counts, ids,
dates and links only: a disaster's GLIDE number, ReliefWeb id, type, countries, status and dates, with a title
Relief writes from those facts, and report counts. Never ReliefWeb's disaster name or description, and never a
report's title, body or source text.
"""
from __future__ import annotations

import json
import urllib.parse
from datetime import datetime, timedelta, timezone

from . import ifrc, iso

API = "https://api.reliefweb.int/v2"
KEY_ENV = "RELIEFWEB_APPNAME"
WEEK_DAYS = 7
BASELINE_WEEKS = 12
COUNTRY_PAGE = "https://reliefweb.int/country/{iso3}"

_DISASTER_FIELDS = ["glide", "status", "date.event", "date.created", "date.changed", "primary_type.name",
                    "primary_type.code", "type.name", "country.iso3", "primary_country.iso3", "url_alias"]


def disasters_url() -> str:
    q = [("limit", "1000"), ("filter[field]", "status"), ("filter[value][]", "ongoing"), ("filter[value][]", "alert"),
         ("filter[operator]", "OR"), ("sort[]", "date.event:desc")] + [("fields[include][]", f) for f in _DISASTER_FIELDS]
    return f"{API}/disasters?" + urllib.parse.urlencode(q)


def _iso(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%S+00:00")


def windows(now: str) -> dict:
    t = datetime.fromisoformat(now.replace("Z", "+00:00")).astimezone(timezone.utc).replace(microsecond=0)
    week = t - timedelta(days=WEEK_DAYS)
    base = week - timedelta(days=WEEK_DAYS * BASELINE_WEEKS)
    return {"week": (_iso(week), _iso(t)), "baseline": (_iso(base), _iso(week))}


def reports_url(frm: str, to: str) -> str:
    q = [("limit", "0"), ("filter[field]", "date.created"), ("filter[value][from]", frm), ("filter[value][to]", to),
         ("facets[0][field]", "primary_country.iso3"), ("facets[0][limit]", "1000"),
         ("facets[1][field]", "disaster.id"), ("facets[1][limit]", "1000")]
    return f"{API}/reports?" + urllib.parse.urlencode(q)


def parse(body: bytes) -> dict:
    doc = json.loads(body)
    if not isinstance(doc, dict) or "data" not in doc:
        raise ValueError("ReliefWeb reply has no data")
    return doc


def facets(doc: dict) -> dict[str, dict[str, int]]:
    out = {}
    for name, f in ((doc.get("embedded") or {}).get("facets") or {}).items():
        if f.get("more"):
            raise ValueError(f"ReliefWeb facet {name} was cut short")
        out[name] = {str(x["value"]): int(x["count"]) for x in f.get("data") or []}
    return out


def _day(s: str | None) -> str | None:
    return s[:10] if s else None


def _utc(s: str | None) -> str | None:
    if not s:
        return None
    return datetime.fromisoformat(s).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def attention(week: int, before: int) -> dict:
    lam = before / BASELINE_WEEKS
    return {"reports_last_7_days": week, "mean_per_week": round(lam, 3), "reports_in_baseline": before,
            "baseline_weeks": BASELINE_WEEKS, "tail_probability": round(ifrc.poisson_tail(week, lam), 4)}


def build(disasters: dict, week: dict, baseline: dict, now: str) -> tuple[list[dict], dict]:
    """(published records, extra). Disasters ReliefWeb marks ongoing or alert, each with its report counts, and one
    record per country whose report count meets RL-IND-4 (the page lists every country's counts)."""
    fw, fb = facets(week), facets(baseline)
    wd, bd = fw.get("disaster.id", {}), fb.get("disaster.id", {})
    wc, bc = fw.get("primary_country.iso3", {}), fb.get("primary_country.iso3", {})
    win = windows(now)
    out = []
    for d in disasters.get("data") or []:
        f = d.get("fields") or {}
        did = str(d.get("id") or f.get("id") or "")
        if not did:
            continue
        ccs = [c for c in (iso.a2(x.get("iso3")) for x in f.get("country") or []) if c]
        pcc = iso.a2((f.get("primary_country") or {}).get("iso3"))
        types = [t.get("name") for t in f.get("type") or [] if t.get("name")]
        glide = f.get("glide") or None
        dates = f.get("date") or {}
        alias = f.get("url_alias") or ""
        out.append({
            "key": f"rw:{did}",
            "lane": "reliefweb",
            "record": "disaster",
            "disaster_id": did,
            "glide": glide,
            "status": f.get("status"),
            "hazard": (f.get("primary_type") or {}).get("name") or (types[0] if types else None),
            "hazard_code": (f.get("primary_type") or {}).get("code"),
            "types": types,
            "countries": ([pcc] if pcc else []) + [c for c in ccs if c != pcc],
            "event_day": _day(dates.get("event")),
            "created_day": _day(dates.get("created")),
            "changed_at": _utc(dates.get("changed")),
            "reports": attention(wd.get(did, 0), bd.get(did, 0)),
            "url": alias if alias.startswith("https://reliefweb.int/disaster/") else f"https://reliefweb.int/taxonomy/term/{did}",
        })
    countries = []
    for code in sorted(set(wc) | set(bc)):
        cc = iso.a2(code)
        if not cc:
            continue
        countries.append({"country": cc, "iso3": code.lower(), **attention(wc.get(code, 0), bc.get(code, 0))})
    out.sort(key=lambda r: (r["event_day"] or "", r["key"]), reverse=True)
    extra = {"disasters": len(out), "reports_last_7_days": sum(wc.values()), "reports_in_baseline": sum(bc.values()),
             "not_a_country": {k: v for k, v in wc.items() if not iso.a2(k)}, "window": win,
             "countries": countries}
    return out, extra


def country_records(extra: dict, unusual) -> list[dict]:
    """Feed records for the countries whose report count meets RL-IND-4 (`unusual` is feed.ind4)."""
    return [{"key": f"rwc:{c['country']}", "lane": "reliefweb", "record": "country", "country": c["country"],
             "countries": [c["country"]], "reports": {k: v for k, v in c.items() if k not in ("country", "iso3")},
             "window": extra.get("window"),
             "url": COUNTRY_PAGE.format(iso3=c["iso3"])}
            for c in extra.get("countries") or [] if unusual(c)]
