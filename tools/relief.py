"""Relief CLI: collect, build and check.

    python tools/relief.py collect               # fetch every lane, write data/snapshot.json
    python tools/relief.py collect --only who    # one or more lanes; the rest keep their last copy
    python tools/relief.py build                 # build site/ from data/snapshot.json
    python tools/relief.py check                 # registers, feed linter, terms scan

collect never falls back to made-up data. A lane that fails keeps its last good copy (from_previous) or stays
empty, and the snapshot's "lanes" block says which.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "doctrine" / "kit" / "python"))

from relief import feed, fetch, ifrc, who_don  # noqa: E402
from tic_doctrine import contract, registers  # noqa: E402
from tic_doctrine.lint import check_header  # noqa: E402

LANES = ["ifrc", "who"]


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


def _lane_ifrc(raw_dir, now, getter):
    today = _today(now)
    active, r1, n_active = _pages("ifrc-go-appeals", ifrc.ACTIVE_URL, raw_dir, getter)
    history, r2, _ = _pages("ifrc-go-appeals", ifrc.HISTORY_URL.format(start=ifrc.baseline_start(today).isoformat()),
                            raw_dir, getter)
    if n_active < 50:
        raise ValueError(f"only {n_active} active appeals: GO's reply looks wrong")
    records, extra = ifrc.build(active, history, today)
    return {"records": records, "extra": extra}, r1 + r2


def _lane_who(raw_dir, now, getter):
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


LANE_FN = {"ifrc": _lane_ifrc, "who": _lane_who}


def collect(root: Path = ROOT, getter=None, only: list[str] | None = None, now: str | None = None) -> dict:
    data_dir = root / "data"
    raw_dir = data_dir / "raw"
    snap_path = data_dir / "snapshot.json"
    prev = json.loads(snap_path.read_text(encoding="utf-8")) if snap_path.exists() else {}
    now = now or fetch.now_utc()
    snap = {"generated_at": now, "method_version": feed.METHOD, "lanes": {}, "records": {}, "extra": {}}
    for lane in LANES:
        prev_lane = (prev.get("lanes") or {}).get(lane) or {}
        keep = lambda: ((prev.get("records") or {}).get(lane, []), (prev.get("extra") or {}).get(lane, {}))  # noqa: E731
        if only and lane not in only:
            snap["records"][lane], snap["extra"][lane] = keep()
            snap["lanes"][lane] = {**prev_lane, "from_previous": True} if prev_lane else {"status": "not run"}
            continue
        try:
            result, recs = LANE_FN[lane](raw_dir, now, getter)
            snap["records"][lane] = result["records"]
            snap["extra"][lane] = result["extra"]
            snap["lanes"][lane] = {"status": "ok", "fetched_at": now, "from_previous": False,
                                   "items": len(result["records"]), "failures": 0,
                                   "fetches": [{k: r[k] for k in ("url", "sha256", "bytes")} for r in recs]}
        except Exception as exc:
            had = bool(prev_lane.get("fetched_at"))
            snap["records"][lane], snap["extra"][lane] = keep() if had else ([], {})
            snap["lanes"][lane] = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"[:300], "failed_at": now,
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
        summ = feed.ifrc_summary(r) if r["lane"] == "ifrc" else feed.who_summary(r)
        rows.append({"id": iid, **{k: v for k, v in r.items() if k != "key"}, "summary": summ,
                     "in_feed": not r.get("past_end_date")})
    ccs = sorted({c for r in records for c in ([r["country"]] if r["lane"] == "ifrc" else r["countries"])})
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
)
URL_IN_TEXT = re.compile(r"https?://[^\s\"'<>)\]]+")
# WHO's notice body fields must never reach the site (WHO's terms: no substantial reproduction).
WHO_BODY_FIELDS = ("Overview", "Epidemiology", "Assessment", "Advice", "Response", "FurtherInformation", "Summary")


def terms_scan(paths: list[Path]) -> list[str]:
    errs = []
    for p in paths:
        txt = p.read_text(encoding="utf-8")
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
        if p.get("tier") != "routine" or p.get("kind") != "observation":
            errs.append(f"{p.get('id')}: this slice publishes routine observations only")
    published = [data / "feed.geojson", data / "snapshot.json"]
    if (data / "ended.geojson").exists():
        published.append(data / "ended.geojson")
    errs += terms_scan(published)
    return errs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Relief: IFRC appeals and WHO outbreak notices.")
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
            print(f"  {lane:5s} {st.get('status')} {st.get('items', '')}"
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
