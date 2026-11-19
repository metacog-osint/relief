"""IFRC GO appeals: Emergency Appeals and DREF allocations, as the IFRC publishes them.

Read from the public GO API (goadmin.ifrc.org/api/v2/appeal/, no key). Two reads each run:
  1. every appeal IFRC marks Active (status=0), whatever its start date;
  2. every appeal that started since BASELINE_START, for each country's own record.
Published: active appeals, plus any appeal that started in the last RECENT_DAYS. The baseline reads are used for
counts only and are never republished (GO's terms: non-commercial use, no copying of the data bank or a
substantial part of it; maps, charts and analyses are allowed).

Amounts are in Swiss francs (CHF), as IFRC states appeals. A DREF allocation is normally funded in full on
approval, so its funded share says little; an Emergency Appeal's funded share is the measure of response.
"""
from __future__ import annotations

import json
import math
from datetime import date, timedelta

API = "https://goadmin.ifrc.org/api/v2/appeal/"
ACTIVE_URL = API + "?status=0&limit=500&ordering=-start_date&format=json"
HISTORY_URL = API + "?start_date__gte={start}&limit=500&ordering=-start_date&format=json"
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


def record(a: dict) -> dict | None:
    """One appeal as Relief keeps it, or None when it has no country (regional appeals)."""
    c = a.get("country") or {}
    cc = (c.get("iso") or "").upper()
    if len(cc) != 2:
        return None
    ev = a.get("event_details") or {}
    ev_id = a.get("event") or ev.get("id")
    req = float(a.get("amount_requested") or 0)
    fund = float(a.get("amount_funded") or 0)
    return {
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
    baseline. It is a measurement of how unusual the count is for this place, not a warning."""
    start = baseline_start(today)
    recent_from = today - timedelta(days=RECENT_DAYS)
    base_days = (recent_from - start).days
    periods = base_days / RECENT_DAYS
    counts: dict[str, list[int]] = {}
    for r in history:
        sd = r.get("start_date")
        if not sd:
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
        r["place_context"] = ctx.get(r["country"])
        out.append(r)
    out.sort(key=lambda r: (r["start_date"] or "", r["appeal_id"]), reverse=True)
    extra = {"active": sum(1 for r in out if r["status"] == "Active"), "published": len(out),
             "baseline_appeals": len(hist), "no_country": skipped,
             "baseline_start": baseline_start(today).isoformat(), "recent_days": RECENT_DAYS}
    return out, extra
