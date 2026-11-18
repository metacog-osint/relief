"""Record small test fixtures from the raw copies of the last collect (data/raw/, git-ignored).

    python tests/make_fixtures.py                       # every lane
    python tests/make_fixtures.py --only hapi reliefweb # some lanes; the others' fixtures stay as they are

The fixtures are cut down on purpose, because the repository may be public and neither publisher allows bulk
reposting: 60 active and 120 baseline IFRC appeals (real records, `next` removed), and 60 WHO notices with every
body field replaced by a marker paragraph (titles, ids and dates are real). The marker keeps WHO's `paraeid`
attribute so the terms scan has something to catch.

HDX HAPI (CC BY-IGO): the funding and needs rows of ten countries, the resources they cite, and each dataset's
licence id from HDX's catalogue (nothing else of the catalogue reply). ReliefWeb (no redistribution): 20 current
disasters with ReliefWeb's name replaced by a marker the terms scan catches, and the two report-count replies,
which are counts only.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "tests" / "fixtures"
BODY = ("Response", "FurtherInformation", "Summary", "Epidemiology", "Advice", "Assessment", "Overview")


def latest(source_id: str, needle: str) -> bytes:
    rows = [json.loads(line) for line in (RAW / "index.jsonl").read_text(encoding="utf-8").splitlines()]
    rows = [r for r in rows if r["source_id"] == source_id and needle in r["url"]]
    if not rows:
        raise SystemExit(f"no raw copy for {source_id} {needle}: run tools/relief.py collect first")
    sha = rows[-1]["sha256"][:12]
    return gzip.decompress((RAW / source_id / f"{sha}.json.gz").read_bytes())


HAPI_COUNTRIES = {"MOZ", "MMR", "SDN", "PSE", "CHL", "AFG", "SSD", "YEM", "UKR", "COD"}
RW_NAME = "[fixture: ReliefWeb name removed]"


def dump(name: str, obj) -> None:
    txt = json.dumps(obj, ensure_ascii=False)
    # ReliefWeb echoes the request URL, appname included, in each reply's href and links; those are dropped below,
    # and no fixture is written while any key value is still in it.
    for env in ("RELIEFWEB_APPNAME", "HDX_HAPI_APP_IDENTIFIER"):
        v = os.environ.get(env)
        if v and (v in txt or urllib.parse.quote(v, safe="") in txt):
            raise SystemExit(f"{name}: {env}'s value is in the fixture; not written")
    if "appname=" in txt:
        raise SystemExit(f"{name}: an appname parameter is in the fixture; not written")
    (OUT / name).write_text(txt, encoding="utf-8")


def strip_echo(doc: dict) -> dict:
    """Drop ReliefWeb's echo of the request URL (it carries the appname)."""
    doc.pop("href", None)
    doc.pop("links", None)
    return doc


def hapi_fixtures() -> None:
    fund = json.loads(latest("hdx-hapi", "coordination-context/funding"))["data"]
    needs = json.loads(latest("hdx-hapi", "humanitarian-needs"))["data"]
    res = json.loads(latest("hdx-hapi", "metadata/resource"))["data"]
    fund = [r for r in fund if r["location_code"] in HAPI_COUNTRIES]
    needs = [r for r in needs if r["location_code"] in HAPI_COUNTRIES and r.get("category") in ("", "total")]
    rids = {r["resource_hdx_id"] for r in fund + needs}
    res = [r for r in res if r["resource_hdx_id"] in rids]
    dump("hapi_funding.json", {"data": fund})
    dump("hapi_needs.json", {"data": needs})
    dump("hapi_resources.json", {"data": res})
    for stub in sorted({r["dataset_hdx_stub"] for r in res}):
        lic = json.loads(latest("hdx-catalogue", f"id={stub}"))["result"]["license_id"]
        dump(f"hdx_package_{stub}.json", {"result": {"name": stub, "license_id": lic}})
    print(f"fixtures: HAPI {len(fund)} funding, {len(needs)} needs rows, {len(res)} resources")


def reliefweb_fixtures() -> None:
    dis = strip_echo(json.loads(latest("reliefweb-api", "/disasters?")))
    dis["data"] = dis["data"][:20]
    for d in dis["data"]:
        for key in ("name", "description", "description-html", "profile"):
            if key in d.get("fields", {}):
                d["fields"][key] = RW_NAME
    dis["count"] = dis["totalCount"] = len(dis["data"])
    dump("rw_disasters.json", dis)
    rows = [json.loads(line) for line in (RAW / "index.jsonl").read_text(encoding="utf-8").splitlines()]
    reps = [r for r in rows if r["source_id"] == "reliefweb-api" and "/reports?" in r["url"]][-2:]
    for name, r in zip(("rw_week.json", "rw_baseline.json"), reps):
        doc = strip_echo(json.loads(gzip.decompress((RAW / "reliefweb-api" / f"{r['sha256'][:12]}.json.gz").read_bytes())))
        doc["data"] = []
        dump(name, doc)
    print(f"fixtures: ReliefWeb {len(dis['data'])} disasters, 2 report-count replies")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", choices=["ifrc", "who", "hapi", "reliefweb"])
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    only = set(args.only or ["ifrc", "who", "hapi", "reliefweb"])
    if "hapi" in only:
        hapi_fixtures()
    if "reliefweb" in only:
        reliefweb_fixtures()
    if not only & {"ifrc", "who"}:
        return
    active = json.loads(latest("ifrc-go-appeals", "status=0"))
    hist = json.loads(latest("ifrc-go-appeals", "start_date__gte"))
    a = active["results"][:60]
    h = hist["results"][:120]
    (OUT / "ifrc_active.json").write_text(json.dumps({"count": len(a), "next": None, "results": a}), encoding="utf-8")
    (OUT / "ifrc_history.json").write_text(json.dumps({"count": len(h), "next": None, "results": h}), encoding="utf-8")
    who = json.loads(latest("who-don", "skip=0").decode("utf-8"))
    vals = who["value"][:60]
    for v in vals:
        for f in BODY:
            if f in v:
                v[f] = '<p paraeid="{fixture}">[fixture: WHO notice text removed]</p>'
    (OUT / "who_p0.json").write_text(json.dumps({"value": vals}, ensure_ascii=False), encoding="utf-8")
    print(f"fixtures: {len(a)} active, {len(h)} baseline appeals, {len(vals)} WHO notices")


if __name__ == "__main__":
    main()
