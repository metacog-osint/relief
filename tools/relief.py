"""Relief CLI: collect, build and check.

    python tools/relief.py collect               # fetch every lane, write data/snapshot.json
    python tools/relief.py collect --only who    # one or more lanes; the rest keep their last copy
    python tools/relief.py build                 # build site/ from data/snapshot.json
    python tools/relief.py check                 # registers, feed linter, terms scan

collect never falls back to made-up data. A lane that fails keeps its last good copy (from_previous) or stays
empty, and the snapshot's "lanes" block says which. The hapi and reliefweb lanes need their keys in the environment
(HDX_HAPI_APP_IDENTIFIER, RELIEFWEB_APPNAME); without one, that lane fails and the others run. Key values never
reach a recorded URL, an error message, the snapshot or the site.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "doctrine" / "kit" / "python"))

from relief import feed, fetch, hapi, ifrc, reliefweb, who_don  # noqa: E402
from tic_doctrine import contract, registers  # noqa: E402
from tic_doctrine.lint import check_header  # noqa: E402

LANES = ["ifrc", "who", "hapi", "reliefweb"]
KEY_NAMES = (hapi.KEY_ENV, reliefweb.KEY_ENV)


def _scrub(text: str, keys: dict) -> str:
    """Remove key values (plain and URL-encoded) from text bound for the snapshot or a log."""
    for name in KEY_NAMES:
        v = keys.get(name)
        if v:
            text = text.replace(v, "<key>").replace(urllib.parse.quote(v, safe=""), "<key>")
    return text


def _today(now: str):
    return datetime.fromisoformat(now.replace("Z", "+00:00")).date()


def _pages(source_id, first_url, raw_dir, getter, limit=20):
    """Follow GO's `next` links. Returns (results, fetch records, count GO states)."""
    url, results, recs, count = first_url, [], [], 0
    for _ in range(limit):
        body, rec = fetch.fetch(source_id, url, raw_dir, "json", timeout=90, getter=getter, gz=True)
        recs.append(rec)
        page, nxt, count = ifrc.parse_page(body)
        results += page
        if not nxt:
            break
        url = nxt
    else:
        raise ValueError(f"more than {limit} pages at {first_url}")
    if count and len(results) < count:
        raise ValueError(f"read {len(results)} of {count} appeals")
    return results, recs, count


def _lane_ifrc(raw_dir, now, getter, keys):
    today = _today(now)
    active, r1, n_active = _pages("ifrc-go-appeals", ifrc.ACTIVE_URL, raw_dir, getter)
    history, r2, _ = _pages("ifrc-go-appeals", ifrc.HISTORY_URL.format(start=ifrc.baseline_start(today).isoformat()),
                            raw_dir, getter)
    if n_active < 50:
        raise ValueError(f"only {n_active} active appeals: GO's reply looks wrong")
    records, extra = ifrc.build(active, history, today)
    return {"records": records, "extra": extra}, r1 + r2


def _lane_who(raw_dir, now, getter, keys):
    values, recs = [], []
    for i in range(who_don.PAGES):
        body, rec = fetch.fetch("who-don", who_don.PAGE_URL.format(skip=100 * i), raw_dir, "json", timeout=90,
                                getter=getter, gz=True)
        recs.append(rec)
        page = who_don.parse_page(body)
        values += page
        if len(page) < 100:
            break
    if len(values) < 50:
        raise ValueError(f"WHO DON read only {len(values)} notices")
    records, extra = who_don.build(values, _today(now))
    return {"records": records, "extra": extra}, recs


def _hapi_pages(url_t, raw_dir, getter, headers, **fmt):
    """Follow HAPI's offset paging (10,000 rows a call), about one call a second as HAPI asks."""
    rows, recs = [], []
    for page in range(10):
        if getter is None:
            time.sleep(1.1)
        body, rec = fetch.fetch("hdx-hapi", url_t.format(offset=10000 * page, **fmt), raw_dir, "json", timeout=120,
                                getter=getter, gz=True, headers=headers)
        recs.append(rec)
        got = hapi.parse(body)
        rows += got
        if len(got) < 10000:
            return rows, recs
    raise ValueError(f"more than 10 pages at {url_t.split('?')[0]}")


def _lane_hapi(raw_dir, now, getter, keys):
    key = keys.get(hapi.KEY_ENV)
    if not key:
        raise RuntimeError(f"{hapi.KEY_ENV} is not set")
    headers = {hapi.HEADER: key}
    today = _today(now)
    start = f"{today.year - 1}-01-01"
    funding, r1 = _hapi_pages(hapi.FUNDING_URL, raw_dir, getter, headers, start=start)
    needs, r2 = _hapi_pages(hapi.NEEDS_URL, raw_dir, getter, headers, start=start)
    resources, r3 = _hapi_pages(hapi.RESOURCE_URL, raw_dir, getter, headers)
    if len(funding) < 50:
        raise ValueError(f"HAPI funding read only {len(funding)} rows")
    res = {r["resource_hdx_id"]: r for r in resources if r.get("resource_hdx_id")}
    stubs = sorted({(res.get(x.get("resource_hdx_id")) or {}).get("dataset_hdx_stub") for x in funding + needs} - {None})
    licences, checked, recs = {}, {}, r1 + r2 + r3
    for stub in stubs:
        try:
            body, rec = fetch.fetch("hdx-catalogue", hapi.HDX_PACKAGE.format(id=stub), raw_dir, "json", timeout=60,
                                    getter=getter, gz=True)
            recs.append(rec)
            licences[stub] = json.loads(body)["result"]["license_id"]
            checked[stub] = {"licence_id": licences[stub], "read": "live"}
        except Exception as exc:  # HDX's catalogue sits behind a bot check that may refuse a runner
            if stub in hapi.RECORDED_LICENCES:
                licences[stub] = hapi.RECORDED_LICENCES[stub]
                checked[stub] = {"licence_id": licences[stub], "read": "recorded 18 Nov 2026",
                                 "error": f"{type(exc).__name__}"[:80]}
            else:
                checked[stub] = {"licence_id": None, "read": "unread", "error": f"{type(exc).__name__}"[:80]}
    records, extra = hapi.build(funding, needs, resources, licences, today)
    extra["licences"] = checked
    if not records:
        raise ValueError("HAPI gave no current-year plan with an open licence")
    return {"records": records, "extra": extra}, recs


def _lane_reliefweb(raw_dir, now, getter, keys):
    key = keys.get(reliefweb.KEY_ENV)
    if not key:
        raise RuntimeError(f"{reliefweb.KEY_ENV} is not set")
    sq = {"appname": key}
    w = reliefweb.windows(now)
    docs, recs = [], []
    for url in (reliefweb.disasters_url(), reliefweb.reports_url(*w["week"]), reliefweb.reports_url(*w["baseline"])):
        body, rec = fetch.fetch("reliefweb-api", url, raw_dir, "json", timeout=90, getter=getter, gz=True,
                                secret_query=sq)
        recs.append(rec)
        docs.append(reliefweb.parse(body))
    dis = docs[0]
    if int(dis.get("totalCount") or 0) > len(dis.get("data") or []):
        raise ValueError("ReliefWeb listed more current disasters than one call returns")
    if len(dis.get("data") or []) < 10:
        raise ValueError(f"ReliefWeb listed only {len(dis.get('data') or [])} current disasters")
    records, extra = reliefweb.build(dis, docs[1], docs[2], now)
    records += reliefweb.country_records(extra, feed.ind4)
    return {"records": records, "extra": extra}, recs


LANE_FN = {"ifrc": _lane_ifrc, "who": _lane_who, "hapi": _lane_hapi, "reliefweb": _lane_reliefweb}


def collect(root: Path = ROOT, getter=None, only: list[str] | None = None, now: str | None = None,
            keys: dict | None = None) -> dict:
    data_dir = root / "data"
    raw_dir = data_dir / "raw"
    snap_path = data_dir / "snapshot.json"
    prev = json.loads(snap_path.read_text(encoding="utf-8")) if snap_path.exists() else {}
    now = now or fetch.now_utc()
    keys = dict(os.environ) if keys is None else keys
    snap = {"generated_at": now, "method_version": feed.METHOD, "lanes": {}, "records": {}, "extra": {}}
    for lane in LANES:
        prev_lane = (prev.get("lanes") or {}).get(lane) or {}
        keep = lambda: ((prev.get("records") or {}).get(lane, []), (prev.get("extra") or {}).get(lane, {}))  # noqa: E731
        if only and lane not in only:
            snap["records"][lane], snap["extra"][lane] = keep()
            snap["lanes"][lane] = {**prev_lane, "from_previous": True} if prev_lane else {"status": "not run"}
            continue
        try:
            result, recs = LANE_FN[lane](raw_dir, now, getter, keys)
            snap["records"][lane] = result["records"]
            snap["extra"][lane] = result["extra"]
            snap["lanes"][lane] = {"status": "ok", "fetched_at": now, "from_previous": False,
                                   "items": len(result["records"]), "failures": 0,
                                   "fetches": [{k: r[k] for k in ("url", "sha256", "bytes")} for r in recs]}
        except Exception as exc:
            had = bool(prev_lane.get("fetched_at"))
            snap["records"][lane], snap["extra"][lane] = keep() if had else ([], {})
            snap["lanes"][lane] = {"status": "failed", "error": _scrub(f"{type(exc).__name__}: {exc}", keys)[:300],
                                   "failed_at": now,
                                   "from_previous": had, "fetched_at": prev_lane.get("fetched_at"),
                                   "items": len(snap["records"][lane]),
                                   "failures": int(prev_lane.get("failures") or 0) + 1}
    data_dir.mkdir(parents=True, exist_ok=True)
    snap_path.write_text(json.dumps(snap, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return snap


def all_records(snap: dict) -> list[dict]:
    return [r for lane in LANES for r in (snap.get("records") or {}).get(lane, [])]


def page_data(snap: dict, records: list[dict], feed_doc: dict) -> dict:
    rows = []
    for r in records:
        iid = feed.item_id(r["key"])
        summ = feed.summary(r, snap["generated_at"])
        hit = feed.rule(r["lane"], r, snap["generated_at"])
        rows.append({"id": iid, **{k: v for k, v in r.items() if k != "key"}, "summary": summ,
                     "in_feed": not r.get("past_end_date"), "unusual": hit["indicator"] if hit else None})
    ccs = sorted({c for r in records for c in ([r["country"]] if r.get("country") else r.get("countries") or [])}
                 | {c["country"] for c in ((snap.get("extra") or {}).get("reliefweb") or {}).get("countries") or []})
    return {"generated_at": snap["generated_at"], "method_version": snap["method_version"], "name": feed.NAME,
            "lanes": {k: {kk: vv for kk, vv in v.items() if kk != "fetches"} for k, v in snap["lanes"].items()},
            "extra": snap.get("extra") or {}, "items": rows,
            "country_names": {c: feed._name(c) for c in ccs}}  # noqa: SLF001


def build_site(root: Path = ROOT, snapshot: dict | None = None) -> dict[str, str]:
    snap_path = root / "data" / "snapshot.json"
    if snapshot is None:
        if not snap_path.exists():
            raise SystemExit("No data/snapshot.json. Run `python tools/relief.py collect` first; "
                             "Relief does not build from made-up data.")
        snapshot = json.loads(snap_path.read_text(encoding="utf-8"))
    snap = snapshot
    records = all_records(snap)
    # The feed (and so COP) carries current appeals only: IFRC keeps many appeals Active long after their end
    # date (205 of 366 on 16 Nov 2026), which is IFRC's housekeeping, not a current need. The page lists them all,
    # marked, so nothing is hidden.
    current = [r for r in records if not r.get("past_end_date")]
    feed_doc = feed.build_feed(current, snap["generated_at"], feed.health(snap.get("lanes") or {}, current))

    def dump(obj) -> str:
        return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"

    files = {"data/feed.geojson": dump(feed_doc), "data/snapshot.json": dump(page_data(snap, records, feed_doc))}
    src_dir = root / "site_src"
    if src_dir.exists():
        for p in sorted(src_dir.rglob("*")):
            if p.is_file():
                files[p.relative_to(src_dir).as_posix()] = p.read_text(encoding="utf-8")
    for p in sorted((root / "doctrine").glob("*.md")):
        files[f"doctrine/{p.name}"] = p.read_text(encoding="utf-8")
    out_dir = root / "site"
    out_dir.mkdir(parents=True, exist_ok=True)
    for rel, txt in files.items():
        dest = out_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(txt, encoding="utf-8", newline="\n")
    return files


# Links the published output may carry: the publishers' own pages and the references we cite.
ALLOWED_URL_PREFIXES = (
    "https://go.ifrc.org/", "https://goadmin.ifrc.org/api/v2/appeal/", "https://www.ifrc.org/",
    "https://www.who.int/emergencies/disease-outbreak-news/", "https://www.who.int/api/news/diseaseoutbreaknews",
    "https://www.who.int/about/policies/", "https://raw.githubusercontent.com/IFRCGo/",
    "https://relief.theintelligence.company", "https://theintelligence.company",
    "https://github.com/metacog-osint/tic-doctrine", "https://creativecommons.org/",
    "https://data.humdata.org/dataset/", "https://reliefweb.int/disaster/", "https://reliefweb.int/country/",
    "https://reliefweb.int/taxonomy/term/",
)
URL_IN_TEXT = re.compile(r"https?://[^\s\"'<>)\]]+")
# WHO's notice body fields must never reach the site (WHO's terms: no substantial reproduction).
WHO_BODY_FIELDS = ("Overview", "Epidemiology", "Assessment", "Advice", "Response", "FurtherInformation", "Summary")
# ReliefWeb's text (terms: no redistribution or compilation) and the fields of the lanes Relief does not publish:
# IPC food-security phases (held for Tom's decision on IPC's terms) and IOM DTM displacement (no redistribution).
RELIEFWEB_TEXT_FIELDS = ("description", "description-html", "body", "body-html", "profile", "headline")
HELD_FIELDS = ("ipc_phase", "ipc_type", "population_in_phase", "population_fraction_in_phase", "reporting_round",
               "assessment_type")
KEY_MARKERS = ("appname=", "app_identifier=", "X-HDX-HAPI-APP-IDENTIFIER")


def terms_scan(paths: list[Path], keys: dict | None = None) -> list[str]:
    keys = dict(os.environ) if keys is None else keys
    secrets = [v for v in (keys.get(n) for n in KEY_NAMES) if v and len(v) >= 6]
    errs = []
    for p in paths:
        txt = p.read_text(encoding="utf-8")
        for f in RELIEFWEB_TEXT_FIELDS + HELD_FIELDS:
            if f'"{f}"' in txt:
                errs.append(f"{p.name}: field {f} is in the published output (ReliefWeb text, IPC or DTM)")
        for m in KEY_MARKERS:
            if m in txt:
                errs.append(f"{p.name}: an API key parameter ({m}) is in the published output")
        if any(s in txt or urllib.parse.quote(s, safe="") in txt for s in secrets):
            errs.append(f"{p.name}: an API key value is in the published output")
        if "[fixture: ReliefWeb" in txt:
            errs.append(f"{p.name}: ReliefWeb text (fixture marker) is in the published output")
        for m in URL_IN_TEXT.finditer(txt):
            if not m.group(0).startswith(ALLOWED_URL_PREFIXES):
                errs.append(f"{p.name}: URL outside the allowed publisher pages: {m.group(0)[:80]}")
        for f in WHO_BODY_FIELDS:
            if f'"{f}"' in txt:
                errs.append(f"{p.name}: WHO body field {f} is in the published output")
        if "paraeid" in txt:  # an attribute in every WHO notice body paragraph
            errs.append(f"{p.name}: WHO notice HTML is in the published output")
    return errs


def check_all(root: Path = ROOT) -> list[str]:
    errs = registers.check(root / "doctrine")
    regs = registers.ids(root / "doctrine")
    data = root / "site" / "data"
    feed_path = data / "feed.geojson"
    if not feed_path.exists():
        return errs + ["site/data/feed.geojson is missing: run collect and build first"]
    doc = json.loads(feed_path.read_text(encoding="utf-8"))
    errs += [f"feed header: {std}: {msg}" for std, sev, msg in check_header(doc) if sev == "error"]
    for feat in doc.get("features", []):
        p = feat.get("properties") or {}
        for std, sev, msg in contract.check(feat, regs):
            if sev == "error":
                errs.append(f"{p.get('id', '?')}: {std}: {msg}")
        if p.get("kind") != "observation" or p.get("tier") not in ("routine", "anomaly"):
            errs.append(f"{p.get('id')}: this slice publishes observations only, tier routine or anomaly")
        # The tier must be what the thresholds say (feed.rule), recomputed from the item's own fields.
        cc0 = (p.get("countries") or [""])[0]
        if p.get("appeal") is not None:
            hit = feed.rule("ifrc", {"place_context": p.get("place_context"), "country": cc0,
                                     "start_date": p["appeal"].get("start_date")}, doc.get("generated_at") or "")
        elif p.get("plan") is not None:
            hit = feed.rule("hapi", {"needs": p.get("needs"), "country": cc0, "year": p["plan"].get("year")},
                            doc.get("generated_at") or "")
        elif p.get("reports") is not None:
            d = p.get("disaster") or {}
            hit = feed.rule("reliefweb", {"reports": p["reports"], "record": "disaster" if d else "country",
                                          "disaster_id": d.get("disaster_id"), "country": cc0},
                            doc.get("generated_at") or "")
        else:
            hit = feed.rule("who", {"prior_notices_730_days": (p.get("notice") or {}).get("prior_notices_730_days")},
                            doc.get("generated_at") or "")
        if (p.get("tier") == "anomaly") != bool(hit):
            errs.append(f"{p.get('id')}: tier {p.get('tier')} does not match the RL-IND-1 to RL-IND-4 thresholds")
    published = [data / "feed.geojson", data / "snapshot.json"]
    if (data / "ended.geojson").exists():
        published.append(data / "ended.geojson")
    errs += terms_scan(published)
    return errs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Relief: IFRC appeals, WHO outbreak notices, UN plans (HDX HAPI) "
                                             "and ReliefWeb disasters.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--only", nargs="*", choices=LANES)
    sub.add_parser("build")
    sub.add_parser("check")
    args = ap.parse_args(argv)
    if args.cmd == "collect":
        snap = collect(only=args.only)
        for lane, st in snap["lanes"].items():
            extra = f" ({st.get('error')})" if st.get("status") == "failed" else ""
            print(f"  {lane:9s} {st.get('status')} {st.get('items', '')}"
                  f"{' [last good copy]' if st.get('from_previous') else ''}{extra}")
        return 0 if any(s.get("status") == "ok" for s in snap["lanes"].values()) else 1
    if args.cmd == "build":
        print(f"Built site/ ({len(build_site(ROOT))} files).")
        return 0
    if args.cmd == "check":
        errs = check_all(ROOT)
        for e in errs[:60]:
            print("  -", e)
        print(f"Relief check: {'PASS' if not errs else f'FAIL ({len(errs)} problems)'}")
        return 1 if errs else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
