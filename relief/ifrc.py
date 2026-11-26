"""IFRC GO appeals: Emergency Appeals and DREF allocations, as the IFRC publishes them.

Read from the public GO API (goadmin.ifrc.org/api/v2/appeal/, no key). Two reads each run:
  1. every appeal IFRC marks Active (status=0), whatever its start date;
  2. every appeal that started since BASELINE_START, for each country's own record.
Published: active appeals, plus any appeal that started in the last RECENT_DAYS. The baseline reads are used for
counts only and are never republished (GO's terms: non-commercial use, no copying of the data bank or a
substantial part of it; maps, charts and analyses are allowed). history/ keeps an index (id, hash, link) and counts;
the full records go to the private archive only (archive.py).

Amounts are in Swiss francs (CHF), as IFRC states appeals. A DREF allocation is normally funded in full on
approval, so its funded share says little; an Emergency Appeal's funded share is the measure of response.

Regional and global appeals. IFRC codes a country's appeal with a three-letter prefix, the country's two-letter
code and a number (MDRKE075). A code without that country part is a regional or global appeal (MDRS1001,
MGR65002, MDR42005, MDRTIGRAY). GO still gives one country for it, often where the appeal is run from (MGR65002,
the Ukraine and impacted countries appeal, is under Hungary, home of IFRC's Europe Regional Office), so that
country is not the place the appeal serves. Such a record keeps GO's country as given and gains `regional` and
`office` (GO's `sector`, the IFRC office named). It is left out of every country's own appeal count, and the
published record names the emergency's countries as GO's emergency record lists them (`countries`).
"""
from __future__ import annotations

import json
import math
import re
from datetime import date, timedelta

API = "https://goadmin.ifrc.org/api/v2/appeal/"
ACTIVE_URL = API + "?status=0&limit=500&ordering=-start_date&format=json"
HISTORY_URL = API + "?start_date__gte={start}&limit=500&ordering=-start_date&format=json"
EVENT_URL = "https://goadmin.ifrc.org/api/v2/event/{id}/?format=json"
COUNTRY_CODE = re.compile(r"^[A-Z]{3}[A-Z]{2}\d")
EMERGENCY_PAGE = "https://go.ifrc.org/emergencies/{id}"
COUNTRY_PAGE = "https://go.ifrc.org/countries/{id}"
BASELINE_YEARS = 10
RECENT_DAYS = 90


def baseline_start(today: date) -> date:
    return date(today.year - BASELINE_YEARS, today.month, min(today.day, 28))


def parse_page(body: bytes) -> tuple[list[dict], str | None, int]:
    doc = json.loads(body)
    if not isinstance(doc, dict) or "results" not in doc:
        raise ValueError("GO reply has no results list")
    return doc["results"], doc.get("next"), int(doc.get("count") or 0)


def _day(s: str | None) -> str | None:
    return s[:10] if s else None


def is_regional(code: str | None) -> bool:
    """True when IFRC's appeal code carries no country: a regional or global appeal."""
    return bool(code) and not COUNTRY_CODE.match(code.strip().upper())


def parse_event(body: bytes) -> list[str]:
    """The countries GO's emergency record lists, as alpha-2 codes in GO's order. Nothing else of it is kept."""
    doc = json.loads(body)
    if not isinstance(doc, dict) or "countries" not in doc:
        raise ValueError("GO emergency reply has no countries list")
    out = []
    for c in doc.get("countries") or []:
        cc = ((c or {}).get("iso") or "").upper()
        if len(cc) == 2 and cc not in out:
            out.append(cc)
    return out


def record(a: dict) -> dict | None:
    """One appeal as Relief keeps it, or None when GO gives it no country (a few regional appeals have a region in
    its place). A regional or global appeal (module notes) gains `regional` and `office`; no other record changes,
    so a country appeal's stored hash stays the same."""
    c = a.get("country") or {}
    cc = (c.get("iso") or "").upper()
    if len(cc) != 2:
        return None
    ev = a.get("event_details") or {}
    ev_id = a.get("event") or ev.get("id")
    req = float(a.get("amount_requested") or 0)
    fund = float(a.get("amount_funded") or 0)
    rec = {
        "key": f"ifrc:{a['id']}",
        "lane": "ifrc",
        "appeal_id": str(a["id"]),
        "code": a.get("code"),
        "name": (a.get("name") or "").strip(),
        "appeal_type": a.get("atype_display"),
        "hazard": ((a.get("dtype") or {}).get("name")),
        "status": a.get("status_display"),
        "country": cc,
        "country_name_ifrc": c.get("name"),
        "region": ((a.get("region") or {}).get("region_name")),
        "start_date": _day(a.get("start_date")),
        "end_date": _day(a.get("end_date")),
        "updated_at": a.get("real_data_update") or a.get("modified_at"),
        "amount_requested_chf": round(req, 2),
        "amount_funded_chf": round(fund, 2),
        "funded_share": round(fund / req, 3) if req > 0 else None,
        "people_targeted": a.get("num_beneficiaries"),
        "emergency_id": str(ev_id) if ev_id else None,
        "emergency_name": (ev.get("name") or "").strip() or None,
        "ifrc_severity": ev.get("ifrc_severity_level_display"),
        "url": EMERGENCY_PAGE.format(id=ev_id) if ev_id else COUNTRY_PAGE.format(id=c.get("id")),
    }
    if is_regional(a.get("code")):
        rec["regional"] = True
        rec["office"] = (a.get("sector") or "").strip() or None
    return rec


def poisson_tail(k: int, lam: float) -> float:
    """P(X >= k) for X ~ Poisson(lam)."""
    if k <= 0:
        return 1.0
    if lam <= 0:
        return 0.0
    term, cdf = math.exp(-lam), 0.0
    for i in range(k):
        if i:
            term *= lam / i
        cdf += term
    return max(0.0, min(1.0, 1.0 - cdf))


def place_context(history: list[dict], today: date) -> dict[str, dict]:
    """For each country: appeals started in the last RECENT_DAYS against its own rate since BASELINE_START.

    The rate is measured on the window before the recent period, so the recent appeals never raise their own
    baseline. It is a measurement of how unusual the count is for this place, not a warning. Regional and global
    appeals are not counted: GO's country for them is where the appeal is recorded, not a place it serves."""
    start = baseline_start(today)
    recent_from = today - timedelta(days=RECENT_DAYS)
    base_days = (recent_from - start).days
    periods = base_days / RECENT_DAYS
    counts: dict[str, list[int]] = {}
    for r in history:
        sd = r.get("start_date")
        if not sd or r.get("regional"):
            continue
        d = date.fromisoformat(sd)
        if d < start or d > today:
            continue
        slot = counts.setdefault(r["country"], [0, 0])
        slot[1 if d >= recent_from else 0] += 1
    out = {}
    for cc, (before, recent) in counts.items():
        lam = before / periods if periods > 0 else 0.0
        out[cc] = {"appeals_last_90_days": recent, "mean_per_90_days": round(lam, 3),
                   "baseline_window": f"{start.isoformat()} to {(recent_from - timedelta(days=1)).isoformat()}",
                   "appeals_in_baseline": before,
                   "tail_probability": round(poisson_tail(recent, lam), 4)}
    return out


def add_countries(records: list[dict], read_event) -> int:
    """Give each published regional record `countries`: the countries of its GO emergency (`read_event(id)` returns
    the reply's bytes), [] when it has no emergency. One read per emergency. Returns the reads made."""
    seen: dict[str, list[str]] = {}
    for r in records:
        if not r.get("regional"):
            continue
        ev = r.get("emergency_id")
        if ev and ev not in seen:
            seen[ev] = parse_event(read_event(ev))
        r["countries"] = list(seen.get(ev, [])) if ev else []
    return len(seen)


def all_records(active: list[dict], history: list[dict]) -> list[dict]:
    """Every appeal read, de-duplicated on appeal id (the set `build` starts from), for the retention archive."""
    by_id: dict[str, dict] = {}
    for a in active + history:
        r = record(a)
        if r is not None:
            by_id.setdefault(r["appeal_id"], r)
    return sorted(by_id.values(), key=lambda r: r["appeal_id"])


def build(active: list[dict], history: list[dict], today: date) -> tuple[list[dict], dict]:
    """(published records, extra). Records are de-duplicated on appeal id."""
    by_id: dict[str, dict] = {}
    skipped = 0
    for a in active + history:
        r = record(a)
        if r is None:
            skipped += 1
            continue
        by_id.setdefault(r["appeal_id"], r)
    hist = [r for r in by_id.values()]
    ctx = place_context(hist, today)
    recent_from = (today - timedelta(days=RECENT_DAYS)).isoformat()
    out = []
    for r in by_id.values():
        if r["status"] != "Active" and (r["start_date"] or "") < recent_from:
            continue
        r = dict(r)
        r["past_end_date"] = bool(r["end_date"] and r["end_date"] < today.isoformat() and r["status"] == "Active")
        r["place_context"] = None if r.get("regional") else ctx.get(r["country"])
        out.append(r)
    out.sort(key=lambda r: (r["start_date"] or "", r["appeal_id"]), reverse=True)
    extra = {"active": sum(1 for r in out if r["status"] == "Active"), "published": len(out),
             "baseline_appeals": len(hist), "no_country": skipped,
             "regional": sum(1 for r in out if r.get("regional")),
             "regional_in_baseline": sum(1 for r in hist if r.get("regional")),
             "baseline_start": baseline_start(today).isoformat(), "recent_days": RECENT_DAYS}
    return out, extra
