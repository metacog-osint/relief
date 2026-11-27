"""HDX HAPI: the UN-coordinated humanitarian plans, what they require and how much is funded (OCHA FTS), and the
people in need and targeted that each country's plan states (OCHA HPC, from the Humanitarian Needs Overviews).

Read from HDX HAPI (hapi.humdata.org/api/v2, the Centre for Humanitarian Data). The app identifier goes in the
X-HDX-HAPI-APP-IDENTIFIER header, never in a URL, and is never recorded. HAPI asks for about one call a second.

    coordination-context/funding           OCHA FTS, dataset global-requirements-and-funding-data, CC BY-IGO
    affected-people/humanitarian-needs     OCHA HPC, dataset global-hpc-hno, CC BY-IGO (admin level 0 only)
    metadata/resource                      the HDX resources behind each row (update date, dataset link)

Each dataset's licence is read from HDX (package_show) every run, and a row is published only when its dataset's
licence is in OPEN_LICENCES. If HDX's catalogue cannot be read, the licence recorded on 18 Nov 2026 is used and the
lane says so. Not read at all: food security (IPC; its terms conflict with HDX's listing), IDPs (IOM DTM: no
redistribution) and conflict events (ACLED's own terms).

Published: one record per plan per country for the current year (FTS's "Not specified" rows, money outside any
plan, are left out), with last year's plan of the same type for that country, and, on the country's own plan, the
intersectoral people in need and targeted against last year's.
"""
from __future__ import annotations

import json
from datetime import date

from . import iso

API = "https://hapi.humdata.org/api/v2"
FUNDING_URL = API + "/coordination-context/funding?output_format=json&limit=10000&offset={offset}&start_date={start}"
NEEDS_URL = (API + "/affected-people/humanitarian-needs?output_format=json&limit=10000&offset={offset}"
             "&admin_level=0&sector_code=Intersectoral&start_date={start}")
RESOURCE_URL = API + "/metadata/resource?output_format=json&limit=10000&offset={offset}"
HDX_PACKAGE = "https://data.humdata.org/api/3/action/package_show?id={id}"
HDX_DATASET = "https://data.humdata.org/dataset/{stub}"  # both checked in a browser 18 Nov 2026
HEADER = "X-HDX-HAPI-APP-IDENTIFIER"
KEY_ENV = "HDX_HAPI_APP_IDENTIFIER"

# Licences that allow free public redistribution with credit (HDX's own licence list, read 18 Nov 2026).
OPEN_LICENCES = {"cc-by-igo": "CC BY-IGO 3.0", "cc-by": "CC BY 4.0", "cc-by-sa": "CC BY-SA 4.0",
                 "odc-odbl": "ODbL 1.0", "odc-by": "ODC-By 1.0", "other-pd-nr": "Public domain (CC0)"}
LICENCE_URL = {"cc-by-igo": "https://creativecommons.org/licenses/by/3.0/igo/",
               "cc-by": "https://creativecommons.org/licenses/by/4.0/",
               "cc-by-sa": "https://creativecommons.org/licenses/by-sa/4.0/"}
# As read from HDX's package_show on 18 Nov 2026, used only when HDX's catalogue cannot be read.
RECORDED_LICENCES = {"global-requirements-and-funding-data": "cc-by-igo", "global-hpc-hno": "cc-by-igo"}
COUNTRY_PLAN_ORDER = ["Humanitarian needs and response plan", "Humanitarian response plan", "Flash appeal", "Other"]
NOT_SPECIFIED = "Not specified"


def parse(body: bytes) -> list[dict]:
    doc = json.loads(body)
    if not isinstance(doc, dict) or not isinstance(doc.get("data"), list):
        raise ValueError("HAPI reply has no data list")
    return doc["data"]


def _day(s: str | None) -> str | None:
    return s[:10] if s else None


def _year(s: str | None) -> int | None:
    return int(s[:4]) if s and s[:4].isdigit() else None


def _share(funded, required):
    return round(funded / required, 3) if required and funded is not None else None


def needs_by_country(rows: list[dict]) -> dict[tuple[str, int], dict]:
    """(alpha-2, year) -> {"people_in_need", "people_targeted", "resource_hdx_id"} from intersectoral rows.

    HPC states a country total with category "total" (2025 resource) or "" (2026 resource). "total" is preferred
    where both exist: in the 2025 resource "" is not always the national total (Myanmar 2025: "" 1,957,173 in need,
    "total" 19,902,649, checked 18 Nov 2026)."""
    best: dict[tuple[str, int, str], tuple[int, dict]] = {}
    for r in rows:
        if r.get("sector_code") != "Intersectoral" or r.get("admin_level") not in (0, None):
            continue
        cat = r.get("category") or ""
        if cat not in ("", "total") or r.get("population_status") not in ("INN", "TGT"):
            continue
        cc, yr = iso.a2(r.get("location_code")), _year(r.get("reference_period_start"))
        if not cc or not yr or r.get("population") is None:
            continue
        rank = 0 if cat == "total" else 1
        k = (cc, yr, r["population_status"])
        if k not in best or rank < best[k][0]:
            best[k] = (rank, r)
    out: dict[tuple[str, int], dict] = {}
    for (cc, yr, st), (_, r) in best.items():
        slot = out.setdefault((cc, yr), {"people_in_need": None, "people_targeted": None, "resource_hdx_id": None})
        slot["people_in_need" if st == "INN" else "people_targeted"] = int(r["population"])
        slot["resource_hdx_id"] = slot["resource_hdx_id"] or r.get("resource_hdx_id")
    return out


def build(funding: list[dict], needs: list[dict], resources: list[dict], licences: dict[str, str],
          today: date) -> tuple[list[dict], dict]:
    """(published records, extra). `licences` maps an HDX dataset stub to its licence id."""
    res = {r["resource_hdx_id"]: r for r in resources if r.get("resource_hdx_id")}

    def meta(rid):
        r = res.get(rid) or {}
        stub = r.get("dataset_hdx_stub")
        lic = licences.get(stub)
        return {"dataset": stub, "dataset_title": r.get("dataset_hdx_title"), "provider": r.get("dataset_hdx_provider_name"),
                "url": HDX_DATASET.format(stub=stub) if stub else None, "updated": r.get("update_date"), "licence_id": lic,
                "licence": OPEN_LICENCES.get(lic or "")}

    year = today.year
    held = {"licence": 0, "no_country": 0, "not_specified": 0, "no_requirement": 0}
    by_year: dict[int, list[dict]] = {}
    for f in funding:
        code = f.get("appeal_code")
        if not code or code == NOT_SPECIFIED:
            held["not_specified"] += 1
            continue
        cc = iso.a2(f.get("location_code"))
        if not cc:
            held["no_country"] += 1
            continue
        if not f.get("requirements_usd"):
            held["no_requirement"] += 1
            continue
        m = meta(f.get("resource_hdx_id"))
        if not m["licence"]:
            held["licence"] += 1
            continue
        yr = _year(f.get("reference_period_start"))
        by_year.setdefault(yr, []).append({**f, "_cc": cc, "_meta": m})
    nd = needs_by_country(needs)

    def prior_plan(cc, atype):
        cands = [p for p in by_year.get(year - 1, []) if p["_cc"] == cc and p.get("appeal_type") == atype]
        if not cands:
            return None
        p = max(cands, key=lambda p: p["requirements_usd"] or 0)
        return {"appeal_code": p["appeal_code"], "requirements_usd": round(p["requirements_usd"]),
                "funding_usd": round(p.get("funding_usd") or 0), "funded_share": _share(p.get("funding_usd") or 0,
                                                                                        p["requirements_usd"])}

    cur = by_year.get(year, [])
    # The plan that carries the country's needs: its own response plan first, then a flash appeal, never a
    # regional plan (those are a country's share of a neighbour's crisis).
    carrier: dict[str, str] = {}
    for atype in COUNTRY_PLAN_ORDER:
        for p in sorted(cur, key=lambda p: -(p["requirements_usd"] or 0)):
            if p.get("appeal_type") == atype and p["_cc"] not in carrier:
                carrier[p["_cc"]] = p["appeal_code"]
    out = []
    for p in cur:
        cc = p["_cc"]
        rec = {
            "key": f"hapi:{p['appeal_code']}:{cc}",
            "lane": "hapi",
            "appeal_code": p["appeal_code"],
            "appeal_name": (p.get("appeal_name") or "").strip(),
            "appeal_type": p.get("appeal_type") or "Other",
            "country": cc,
            "year": year,
            "period_start": _day(p.get("reference_period_start")),
            "period_end": _day(p.get("reference_period_end")),
            "requirements_usd": round(p["requirements_usd"]),
            "funding_usd": round(p.get("funding_usd") or 0),
            "funded_share": _share(p.get("funding_usd") or 0, p["requirements_usd"]),
            "prior_year_plan": prior_plan(cc, p.get("appeal_type")),
            "needs": None,
            "funding_source": p["_meta"],
            "url": p["_meta"]["url"],
        }
        if carrier.get(cc) == p["appeal_code"] and (cc, year) in nd:
            now_n, before = nd[(cc, year)], nd.get((cc, year - 1)) or {}
            nm = meta(now_n["resource_hdx_id"])
            if nm["licence"]:
                pin, prev = now_n["people_in_need"], before.get("people_in_need")
                rec["needs"] = {
                    "year": year, "people_in_need": pin, "people_targeted": now_n["people_targeted"],
                    "people_in_need_prior_year": prev, "people_targeted_prior_year": before.get("people_targeted"),
                    "people_in_need_change": round(pin / prev - 1, 3) if pin is not None and prev else None,
                    "source": nm}
            else:
                held["licence"] += 1
        out.append(rec)
    out.sort(key=lambda r: (-r["requirements_usd"], r["key"]))
    extra = {"year": year, "published": len(out), "plans": len({r["appeal_code"] for r in out}),
             "countries": len({r["country"] for r in out}), "with_needs": sum(1 for r in out if r["needs"]),
             "requirements_usd": sum(r["requirements_usd"] for r in out),
             "funding_usd": sum(r["funding_usd"] for r in out), "left_out": held,
             "funding_rows_read": len(funding), "needs_rows_read": len(needs)}
    return out, extra
