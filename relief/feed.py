"""Build Relief's contract-v2 feed (tic-feed/2, GeoJSON) from the collected records.

One item per IFRC appeal and per WHO outbreak notice: kind "observation", status_class "reported". Each is the
publisher's own report (source grade A2). No probability is stated. Tier is "routine" unless an indicator's
threshold is met (Tom, 16 Nov 2026), then "anomaly", a measurement against the place's own past, never a warning:

- RL-IND-1: an appeal that started in the last 90 days, in a country with at least 2 appeals in those 90 days and
  a Poisson tail probability below 0.01 at that country's rate over the ten years before (`place_context`).
- RL-IND-2: a WHO notice naming a country WHO had not named in the 730 days before (`prior_notices_730_days`).
- RL-IND-3: a country's UN-coordinated plan whose intersectoral people in need is at least 25% above last year's
  plan for that country (`needs`, from OCHA HPC via HDX HAPI). Tom, 18 Nov 2026.
- RL-IND-4: a ReliefWeb disaster, or a country as ReliefWeb's main country of a report, with at least 10 reports in
  the last 7 days and a Poisson tail probability below 0.01 at its own weekly mean over the 12 weeks before
  (`reports`). Tom, 18 Nov 2026.

`rule()` is the one statement of all four; the build and `check` both call it.
"""
from __future__ import annotations

import hashlib
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "doctrine" / "kit" / "python"))
from tic_doctrine import CONTRACT, geo  # noqa: E402

from . import places  # noqa: E402

PROGRAM = "relief"
NAME = "Relief"  # Tom, 15 Nov 2026
SITE = "https://relief.theintelligence.company"  # planned address; no DNS or Pages project yet
METHOD = "relief-0.3"  # 0.2: RL-IND-1/2 set (Tom, 16 Nov 2026); 0.3: HAPI and ReliefWeb lanes, RL-IND-3/4 (18 Nov)
LANGUAGE_KEY = "https://github.com/metacog-osint/tic-doctrine/blob/main/docs/language-key.md"

SOURCES = {
    "ifrc": {"id": "ifrc-go-appeals", "publisher": "International Federation of Red Cross and Red Crescent "
                                                   "Societies (IFRC), GO platform",
             "licence": "IFRC GO terms: non-commercial use with credit; analyses allowed; the data bank is not "
                        "copied or redistributed in bulk",
             "independence_group": "ifrc", "source_type": "humanitarian organisation (own appeals)",
             "descriptor": "IFRC's own record of an Emergency Appeal or DREF allocation it launched: hazard, "
                           "country, amounts requested and funded in CHF, people targeted, dates."},
    "who": {"id": "who-don", "publisher": "World Health Organization (WHO), Disease Outbreak News",
            "licence": "WHO website terms: extracts for research with acknowledgement of WHO, not for commercial "
                       "use; title, date and link only, no notice text republished",
            "independence_group": "who", "source_type": "official notice (UN agency)",
            "descriptor": "WHO's Disease Outbreak News notice of an acute public health event, usually after a "
                          "member state's notification under the International Health Regulations."},
    "hapi": {"id": "hdx-hapi", "publisher": "OCHA Financial Tracking Service (FTS), via HDX HAPI (OCHA Centre for "
                                            "Humanitarian Data)",
             "licence": "CC BY-IGO 3.0 (HDX dataset global-requirements-and-funding-data): credit OCHA FTS, link the "
                        "licence, say what was changed",
             "licence_url": "https://creativecommons.org/licenses/by/3.0/igo/",
             "independence_group": "ocha-fts", "source_type": "UN coordination body (funding records)",
             "descriptor": "OCHA FTS's record of a UN-coordinated humanitarian plan or appeal for a country: what it "
                           "requires and how much funding has been reported against it, in US dollars."},
    "reliefweb": {"id": "reliefweb-api", "publisher": "ReliefWeb (OCHA)",
                  "licence": "ReliefWeb terms and conditions: personal, non-commercial use; no redistribution or "
                             "compilation, so counts, ids, dates and links only, no ReliefWeb text",
                  "independence_group": "reliefweb", "source_type": "UN information service (disaster tracking)",
                  "descriptor": "ReliefWeb's own record of a disaster it tracks (GLIDE number, type, countries, "
                                "status, dates) and the number of reports it posted, counted by Relief."},
}
NEEDS_SOURCE = {"id": "hdx-hapi-needs", "publisher": "OCHA Humanitarian Programme Cycle (Humanitarian Needs "
                                                     "Overviews), via HDX HAPI",
                "licence": "CC BY-IGO 3.0 (HDX dataset global-hpc-hno): credit OCHA, link the licence, say what was "
                           "changed",
                "licence_url": "https://creativecommons.org/licenses/by/3.0/igo/",
                "independence_group": "ocha-hpc", "source_type": "UN coordination body (needs assessment)",
                "descriptor": "OCHA's intersectoral count of people in need and people targeted in a country's "
                              "humanitarian response plan, from its Humanitarian Needs Overview."}
REQUIREMENT = {"ifrc": ["RL-PIR-1", "RL-PIR-2", "RL-EEI-1"], "who": ["RL-PIR-3"],
               "hapi": ["RL-PIR-4", "RL-EEI-2"], "reliefweb": ["RL-PIR-5", "RL-EEI-3"]}


# Thresholds, Tom 16 Nov 2026 ("Adopt both thresholds").
IND1_P = 0.01        # RL-IND-1: tail probability strictly below this
IND1_MIN = 2         # RL-IND-1: at least this many appeals in the window
RECENT_DAYS = 90     # the window place_context counts (ifrc.RECENT_DAYS)
IND3_RISE = 0.25     # RL-IND-3: people in need at least 25% above last year's plan (Tom, 18 Nov 2026)
IND4_MIN = 10        # RL-IND-4: at least this many reports in 7 days (Tom, 18 Nov 2026)
IND4_P = 0.01        # RL-IND-4: tail probability strictly below this


def recent_from(generated: str) -> str:
    """First day of the 90-day window for a collection at `generated` (ISO UTC)."""
    return (date.fromisoformat(generated[:10]) - timedelta(days=RECENT_DAYS)).isoformat()


def ind1(pc: dict | None, start_date: str | None, window_start: str) -> bool:
    return bool(pc and start_date and start_date >= window_start
                and pc.get("appeals_last_90_days", 0) >= IND1_MIN
                and pc.get("tail_probability") is not None and pc["tail_probability"] < IND1_P)


def ind2(prior: dict | None) -> list[str]:
    """Countries in the notice that WHO had not named in the 730 days before (empty if the read is too short)."""
    return sorted(cc for cc, n in (prior or {}).items() if n == 0)


def ind3(needs: dict | None) -> bool:
    if not needs:
        return False
    pin, prev = needs.get("people_in_need"), needs.get("people_in_need_prior_year")
    return bool(pin is not None and prev and pin >= prev * (1 + IND3_RISE))


def ind4(rep: dict | None) -> bool:
    return bool(rep and rep.get("reports_last_7_days", 0) >= IND4_MIN
                and rep.get("tail_probability") is not None and rep["tail_probability"] < IND4_P)


def rule(lane: str, r: dict, generated: str) -> dict | None:
    """The anomaly a record meets, or None. `r` is a collected record (or an item's equivalent fields)."""
    if lane == "hapi":
        if not ind3(r.get("needs")):
            return None
        return {"indicator": "RL-IND-3",
                "baseline_ref": {"id": f"relief-hpc-needs-{r['country']}", "type": "fixed", "version": METHOD,
                                 "window": f"the country's {int(r['year']) - 1} plan"}}
    if lane == "reliefweb":
        rp = r.get("reports")
        if not ind4(rp):
            return None
        tag = f"disaster-{r['disaster_id']}" if r.get("record") == "disaster" else f"country-{r['country']}"
        return {"indicator": "RL-IND-4",
                "baseline_ref": {"id": f"relief-reliefweb-reports-{tag}", "type": "rolling", "version": METHOD,
                                 "window": "the 12 weeks before the last 7 days"}}
    if lane == "ifrc":
        pc = r.get("place_context")
        if not ind1(pc, r.get("start_date"), recent_from(generated)):
            return None
        return {"indicator": "RL-IND-1",
                "baseline_ref": {"id": f"relief-ifrc-appeals-{r['country']}", "type": "rolling", "version": METHOD,
                                 "window": f"{pc['baseline_window']}: the ten years before the last 90 days"}}
    first = ind2(r.get("prior_notices_730_days"))
    if not first:
        return None
    return {"indicator": "RL-IND-2", "countries": first,
            "baseline_ref": {"id": "relief-who-don-" + "-".join(first), "type": "rolling", "version": METHOD,
                             "window": "the 730 days before the notice"}}


def _pct(p: float) -> str:
    return "under 0.1%" if p < 0.001 else f"{p * 100:.1f}%"


def item_id(key: str) -> str:
    lane = key.split(":", 1)[0]
    return f"RL-{lane.upper()}-{hashlib.sha256(key.encode('utf-8')).hexdigest()[:10]}"


def _geometry(ccs: list[str]):
    pts = []
    for cc in ccs:
        p = places.point(cc)
        if p:
            pts.append([p[1], p[0]])
    if not pts:
        return None
    return {"type": "Point", "coordinates": pts[0]} if len(pts) == 1 else {"type": "MultiPoint", "coordinates": pts}


def _name(cc: str) -> str:
    return geo.name(cc) or {"RE": "Réunion", "YT": "Mayotte", "GP": "Guadeloupe", "MQ": "Martinique",
                            "GF": "French Guiana"}.get(cc, cc)


def _day_text(d: str | None) -> str:
    if not d:
        return "an unstated date"
    x = date.fromisoformat(d)
    return f"{x.day} {x.strftime('%b %Y')}"


def _utc(ts: str | None) -> str | None:
    """'2026-11-10 17:24:01+00:00' or '...Z' -> '2026-11-10T17:24:01Z' (seconds kept, fractions dropped)."""
    if not ts:
        return None
    s = ts.replace(" ", "T")
    s = s.split("+")[0].rstrip("Z").split(".")[0]
    return s + "Z" if len(s) >= 19 else None


def _chf(x: float) -> str:
    return f"CHF {x:,.0f}"


def ifrc_summary(r: dict, generated: str | None = None) -> str:
    kind = {"DREF": "a DREF allocation", "Emergency Appeal": "an Emergency Appeal"}.get(r["appeal_type"],
                                                                                       f"an appeal ({r['appeal_type']})")
    bits = [f"IFRC launched {kind} for {_name(r['country'])}"
            + (f" ({r['hazard']})" if r.get("hazard") else "") + f" on {_day_text(r['start_date'])}."]
    money = f"{_chf(r['amount_requested_chf'])} requested"
    if r.get("funded_share") is not None:
        money += f", {_chf(r['amount_funded_chf'])} funded ({r['funded_share']:.0%})"
    if r.get("people_targeted"):
        money += f", {r['people_targeted']:,} people targeted"
    bits.append(money[0].upper() + money[1:] + ".")
    if r["status"] == "Active":
        bits.append(f"Active; IFRC lists the end date as {_day_text(r['end_date'])}"
                    + (", which has passed" if r.get("past_end_date") else "") + ".")
    else:
        bits.append(f"Status: {r['status']}.")
    pc = r.get("place_context")
    if pc:
        bits.append(f"{_name(r['country'])} has had {pc['appeals_last_90_days']} IFRC appeal"
                    f"{'' if pc['appeals_last_90_days'] == 1 else 's'} start in the last 90 days, against an average "
                    f"of {pc['mean_per_90_days']:.2f} per 90 days over {pc['baseline_window']}.")
        if generated and rule("ifrc", r, generated):
            bits.append(f"Unusual for {_name(r['country'])} (RL-IND-1): at that average, the chance of "
                        f"{pc['appeals_last_90_days']} or more in 90 days is {_pct(pc['tail_probability'])}, below "
                        f"the 1% threshold.")
    return " ".join(bits)


def who_summary(r: dict) -> str:
    where = ", ".join([_name(c) for c in r["countries"]] + r["regions"]) or r.get("place") or "no place stated"
    bits = [f"WHO published a Disease Outbreak News notice on {_day_text(r['published_day'])}: {r['disease']}, "
            f"{where}."]
    prior = r.get("prior_notices_730_days")
    if prior:
        for cc, n in prior.items():
            bits.append(f"First WHO notice naming {_name(cc)} in two years." if n == 0 else
                        f"WHO's {n + 1}{_ordinal(n + 1)} notice naming {_name(cc)} in two years.")
    if ind2(prior):
        bits.append(f"Relief marks this unusual for {', '.join(_name(c) for c in ind2(prior))} (RL-IND-2).")
    bits.append("WHO publishes a notice after it has verified the event, often weeks after the first report.")
    return " ".join(bits)


def _usd(x: float | None) -> str:
    return "USD " + (f"{x / 1e9:,.2f} billion" if x and x >= 1e9 else f"{x / 1e6:,.1f} million" if x and x >= 1e6
                     else f"{(x or 0):,.0f}")


def hapi_title(r: dict) -> str:
    name = r["appeal_name"] or r["appeal_code"]
    if r["appeal_type"] == "Regional response plan":
        name += f" ({_name(r['country'])})"
    return f"UN humanitarian plan: {name}"


def hapi_summary(r: dict) -> str:
    bits = [f"OCHA's Financial Tracking Service records {r['appeal_name'] or r['appeal_code']} ({r['appeal_type']}, "
            f"{r['year']}) for {_name(r['country'])}: {_usd(r['requirements_usd'])} required, "
            f"{_usd(r['funding_usd'])} funded"
            + (f" ({r['funded_share']:.0%})." if r.get("funded_share") is not None else ".")]
    pp = r.get("prior_year_plan")
    if pp:
        bits.append(f"Last year's plan of this type ({pp['appeal_code']}): {_usd(pp['requirements_usd'])} required, "
                    + (f"{pp['funded_share']:.0%} funded." if pp.get("funded_share") is not None else "funding unstated."))
    n = r.get("needs")
    if n and n.get("people_in_need") is not None:
        s = f"The plan counts {n['people_in_need']:,} people in need"
        if n.get("people_targeted"):
            s += f" and targets {n['people_targeted']:,}"
        s += f" in {n['year']}"
        if n.get("people_in_need_prior_year"):
            ch = n["people_in_need"] / n["people_in_need_prior_year"] - 1
            s += f", against {n['people_in_need_prior_year']:,} in need in {n['year'] - 1} ({ch:+.0%})"
        bits.append(s + ".")
        if ind3(n):
            bits.append(f"Unusual for {_name(r['country'])} (RL-IND-3): people in need are at least 25% above last "
                        f"year's plan.")
    bits.append("FTS counts the funding reported to it against the plan.")
    return " ".join(bits)


def rw_title(r: dict) -> str:
    if r.get("record") == "country":
        return f"ReliefWeb reporting on {_name(r['country'])}: {r['reports']['reports_last_7_days']} reports in 7 days"
    return f"ReliefWeb disaster: {r.get('hazard') or 'disaster'}, {_where(r['countries'])}, from " \
           f"{_day_text(r.get('event_day'))}"


def _where(ccs: list[str], most: int = 3) -> str:
    names = [_name(c) for c in ccs]
    if not names:
        return "no country stated"
    return ", ".join(names) if len(names) <= most else ", ".join(names[:most]) + f" and {len(names) - most} more"


def rw_summary(r: dict) -> str:
    rp = r["reports"]
    count = (f"{rp['reports_last_7_days']} report{'' if rp['reports_last_7_days'] == 1 else 's'} in the last 7 days, "
             f"against an average of {rp['mean_per_week']:.2f} per week over the {rp['baseline_weeks']} weeks before")
    if r.get("record") == "country":
        bits = [f"ReliefWeb posted {count}, with {_name(r['country'])} as the main country of the report."]
    else:
        where = ", ".join(_name(c) for c in r["countries"]) or "no country stated"
        bits = [f"ReliefWeb tracks this disaster ({r.get('hazard') or 'type not stated'}) in {where}"
                + (f", GLIDE {r['glide']}" if r.get("glide") else "")
                + f"; event date {_day_text(r.get('event_day'))}, status {r.get('status')}.",
                f"ReliefWeb posted {count.replace(' in the last 7 days', ' on it in the last 7 days', 1)}."]
    if ind4(rp):
        bits.append(f"Unusual (RL-IND-4): at that average, the chance of {rp['reports_last_7_days']} or more in a "
                    f"week is {_pct(rp['tail_probability'])}, below the 1% threshold.")
    bits.append("A count of reports measures reporting attention, not need.")
    return " ".join(bits)


def summary(r: dict, generated: str) -> str:
    lane = r["lane"]
    if lane == "ifrc":
        return ifrc_summary(r, generated)
    if lane == "who":
        return who_summary(r)
    if lane == "hapi":
        return hapi_summary(r)
    return rw_summary(r)


def _ordinal(n: int) -> str:
    return "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def feature(r: dict, generated: str) -> dict:
    lane = r["lane"]
    src = dict(SOURCES[lane])
    src.update({"url": r["url"], "grade": "A2", "accessed_at": generated})
    iid = item_id(r["key"])
    hit = rule(lane, r, generated)
    common = {
        "contract": CONTRACT, "id": iid, "program": PROGRAM, "kind": "observation",
        "tier": "anomaly" if hit else "routine",
        "status": "actual", "msg_type": "new", "human_review": "none", "us_person_data": "none",
        "status_class": "reported", "product_category": "current", "published_at": generated,
        "pmesii_pt": ["social"], "ie_aspect": ["physical", "human"], "ascope": ["people", "events"],
        "requirement_ids": REQUIREMENT[lane], "method_version": METHOD,
        "visual": {"type": "page", "url": f"{SITE}/#{iid}"},
    }
    if hit:
        common["baseline_ref"] = hit["baseline_ref"]
    if lane == "ifrc":
        src["title"] = f"{r['appeal_type']} {r['code']}: {r['name']}"
        props = {**common,
                 "title": f"{r['appeal_type']}: {r['name']}",
                 "summary": ifrc_summary(r, generated),
                 "data_as_of": _utc(r.get("updated_at")) or f"{r['start_date']}T00:00:00Z",
                 "countries": [r["country"]],
                 "precision_class": "country",
                 "coverage_fraction": 1.0,
                 "sources": [src],
                 "appeal": {k: r.get(k) for k in (
                     "appeal_id", "code", "appeal_type", "hazard", "status", "start_date", "end_date",
                     "past_end_date", "amount_requested_chf", "amount_funded_chf", "funded_share", "people_targeted",
                     "emergency_id", "emergency_name", "ifrc_severity", "region")},
                 "place_context": r.get("place_context")}
        if not _utc(r.get("updated_at")):
            props["data_as_of_precision"] = "day"
        geom = _geometry([r["country"]])
    elif lane == "hapi":
        fs = r.get("funding_source") or {}
        src.update({"title": f"FTS: {r['appeal_code']} {r['appeal_name']}", "url": r["url"]})
        if fs.get("licence"):
            src["licence"] = f"{fs['licence']} (HDX dataset {fs.get('dataset')}): credit OCHA FTS, link the licence, " \
                             "say what was changed"
        sources = [src]
        n = r.get("needs")
        if n:
            ns = dict(NEEDS_SOURCE)
            ns.update({"url": (n.get("source") or {}).get("url"), "grade": "A2", "accessed_at": generated,
                       "title": f"HPC needs, {_name(r['country'])} {n['year']}"})
            sources.append(ns)
        props = {**common,
                 "title": hapi_title(r),
                 "summary": hapi_summary(r),
                 "data_as_of": _utc(fs.get("updated")) or f"{r['period_start']}T00:00:00Z",
                 "countries": [r["country"]],
                 "precision_class": "country",
                 "coverage_fraction": 1.0,
                 "sources": sources,
                 "plan": {k: r.get(k) for k in ("appeal_code", "appeal_name", "appeal_type", "year", "period_start",
                                                "period_end", "requirements_usd", "funding_usd", "funded_share",
                                                "prior_year_plan")},
                 "needs": {k: v for k, v in n.items() if k != "source"} if n else None}
        if not _utc(fs.get("updated")):
            props["data_as_of_precision"] = "day"
        geom = _geometry([r["country"]])
    elif lane == "reliefweb":
        src["title"] = rw_title(r)
        props = {**common,
                 "title": rw_title(r),
                 "summary": rw_summary(r),
                 "data_as_of": generated if r.get("record") == "country" else (r.get("changed_at") or generated),
                 "countries": r["countries"],
                 "precision_class": "country" if r["countries"] else "none",
                 "coverage_fraction": 1.0,
                 "sources": [src],
                 "reports": r["reports"]}
        if r.get("record") == "country":
            props["status_class"] = "assessed"   # Relief's own count of ReliefWeb's posts
            props["reporting"] = {"country": r["country"], "window": r.get("window")}
        else:
            props["disaster"] = {k: r.get(k) for k in ("disaster_id", "glide", "status", "hazard", "hazard_code",
                                                       "types", "event_day", "created_day")}
        geom = _geometry(r["countries"])
    else:
        src["title"] = r["title"]
        src["published_at"] = f"{r['published_day']}T00:00:00Z"
        props = {**common,
                 "title": f"WHO outbreak notice: {r['title']}",
                 "summary": who_summary(r),
                 "data_as_of": f"{r['published_day']}T00:00:00Z",
                 "data_as_of_precision": "day",
                 "countries": r["countries"],
                 "precision_class": "country" if r["countries"] else "none",
                 "coverage_fraction": 1.0 if r["place_parsed"] else 0.0,
                 "sources": [src],
                 "notice": {k: r.get(k) for k in ("don_id", "disease", "place", "regions", "place_unread",
                                                  "prior_notices_730_days")}}
        geom = _geometry(r["countries"])
    return {"type": "Feature", "geometry": geom, "properties": props}


def _day_only(ts: str | None) -> str | None:
    return ts[:10] if ts else None


def health(lanes: dict, records: list[dict]) -> dict:
    """Per-source health, keyed by the source id the items carry (the key the kit's history log and COP read),
    in Cordon's, Headwind's and Undertow's shape. State is "up" when the lane was read on its last run and
    "failing" when not; its last good items stay in the feed."""
    newest: dict[str, str] = {}
    for r in records:
        d = {"ifrc": lambda: r.get("start_date"), "who": lambda: r.get("published_day"),
             "hapi": lambda: _day_only((r.get("funding_source") or {}).get("updated")),
             "reliefweb": lambda: _day_only(r.get("changed_at"))}[r["lane"]]()
        if d and d > newest.get(r["lane"], ""):
            newest[r["lane"]] = d
    out = {}
    for lane, src in SOURCES.items():
        st = lanes.get(lane) or {}
        ok, failed = st.get("status") == "ok", st.get("status") == "failed"
        n = st.get("items") or 0
        if ok:
            detail = f"{n} items" + (" (last good copy, not read on this run)" if st.get("from_previous") else "")
        elif failed:
            detail = (f"not read; {n} items from the last good copy" if st.get("from_previous")
                      else "not read; no earlier copy, so no items")
        else:
            detail = "not run yet"
        out[src["id"]] = {
            "state": "up" if ok else "failing",
            "last_ok": st.get("fetched_at"),
            "last_error": st.get("error") if failed else None,
            "failures": int(st.get("failures") or 0) if (ok or failed) else 0,
            "checked_at": st.get("failed_at") if failed else st.get("fetched_at"),
            "detail": detail,
            "lane": lane,
            "data_as_of": f"{newest[lane]}T00:00:00Z" if lane in newest else None,
        }
    return out


def build_feed(records: list[dict], generated: str, health_record: dict | None = None) -> dict:
    feats = [feature(r, generated) for r in records]
    feats.sort(key=lambda f: (f["properties"]["data_as_of"], f["properties"]["id"]), reverse=True)
    doc = {
        "type": "FeatureCollection",
        "contract": CONTRACT,
        "program": PROGRAM,
        "generated_at": generated,
        "method_version": METHOD,
        "licence": ("Relief's own text: CC BY 4.0 (The Intelligence Company). Each item keeps its source's "
                    "terms: IFRC GO, non-commercial use with credit, no bulk redistribution; WHO, extracts for "
                    "research with acknowledgement, title, date and link only; OCHA FTS and OCHA HPC via HDX HAPI, "
                    "CC BY-IGO 3.0 (https://creativecommons.org/licenses/by/3.0/igo/), amounts and counts as "
                    "published, with Relief's shares and changes added; ReliefWeb, counts, ids, dates and links "
                    "only."),
        "attribution": ("Relief, The Intelligence Company. Sources: IFRC GO "
                        "(International Federation of Red Cross and Red Crescent Societies); WHO Disease Outbreak "
                        "News (World Health Organization); OCHA Financial Tracking Service and OCHA Humanitarian "
                        "Programme Cycle, via the HDX Humanitarian API (OCHA Centre for Humanitarian Data); "
                        "ReliefWeb (OCHA)."),
        "language_key": LANGUAGE_KEY,
        "note": ("Measurements and publishers' reports only: no probability, no warning. Tier anomaly marks a "
                 "count unusual for that place against its own past (RL-IND-1 to RL-IND-4), not a warning. IFRC appeals show where the "
                 "Red Cross and Red Crescent asked for money, not every place in need: crises led by the ICRC, the "
                 "UN or governments may have no IFRC appeal."),
    }
    if health_record is not None:
        doc["health"] = health_record
    doc["features"] = feats
    return doc
