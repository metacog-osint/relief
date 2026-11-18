"""Offline tests on cut-down recorded replies (tests/make_fixtures.py). Standard library only.

    python -m unittest discover -s tests
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
import urllib.parse
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "doctrine" / "kit" / "python"))

import importlib.util  # noqa: E402

from relief import feed, hapi, ifrc, iso, places, reliefweb, who_don  # noqa: E402

# The CLI (tools/relief.py) shares its name with the package, so it is loaded by path, not by import.
_spec = importlib.util.spec_from_file_location("relief_cli", ROOT / "tools" / "relief.py")
cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cli)
from tic_doctrine import contract, registers  # noqa: E402

FIX = ROOT / "tests" / "fixtures"
NOW = "2026-11-16T02:00:00Z"
KEYS = {"HDX_HAPI_APP_IDENTIFIER": "test-hapi-identifier", "RELIEFWEB_APPNAME": "test-relief-appname"}
SEEN: list[str] = []


def getter(url: str, timeout: int) -> bytes:
    SEEN.append(url)
    for k in KEYS.values():
        assert k not in url, "a key reached a URL the getter (and the raw index) sees"
    if "hapi.humdata.org" in url:
        if "offset=0" not in url:
            return json.dumps({"data": []}).encode()
        name = ("hapi_funding.json" if "coordination-context/funding" in url else
                "hapi_needs.json" if "humanitarian-needs" in url else "hapi_resources.json")
        return (FIX / name).read_bytes()
    if "data.humdata.org/api/3/action/package_show" in url:
        stub = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["id"][0]
        return (FIX / f"hdx_package_{stub}.json").read_bytes()
    if "api.reliefweb.int" in url:
        if "/disasters?" in url:
            return (FIX / "rw_disasters.json").read_bytes()
        frm = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["filter[value][from]"][0]
        return (FIX / ("rw_week.json" if frm == reliefweb.windows(NOW)["week"][0] else "rw_baseline.json")).read_bytes()
    if "goadmin.ifrc.org" in url:
        return (FIX / ("ifrc_active.json" if "status=0" in url else "ifrc_history.json")).read_bytes()
    if "who.int/api" in url:
        if "skip=0" in url:
            return (FIX / "who_p0.json").read_bytes()
        return json.dumps({"value": []}).encode()
    raise AssertionError(f"unexpected URL {url}")


def failing(url: str, timeout: int) -> bytes:
    raise OSError("network down")


def catalogue_down(url: str, timeout: int) -> bytes:
    if "data.humdata.org" in url:
        raise OSError("bot check")
    return getter(url, timeout)


def leaky(url: str, timeout: int) -> bytes:
    if "api.reliefweb.int" in url:
        raise OSError(f"refused for {KEYS['RELIEFWEB_APPNAME']}")
    return getter(url, timeout)


class Places(unittest.TestCase):
    CASES = [
        ("Middle East respiratory syndrome (MERS) – Qatar", "Middle East respiratory syndrome (MERS)", ["QA"], []),
        ("Ebola disease caused by Bundibugyo virus, Democratic Republic of the Congo, Kenya and Nigeria",
         "Ebola disease caused by Bundibugyo virus", ["CD", "KE", "NG"], []),
        ("Sudan virus disease – Uganda", "Sudan virus disease", ["UG"], []),
        ("Marburg Virus Disease–United Republic of Tanzania", "Marburg Virus Disease", ["TZ"], []),
        ("Human infection caused by avian Influenza A(H5N2)-Mexico", "Human infection caused by avian Influenza A(H5N2)",
         ["MX"], []),
        ("COVID-19 - Global Situation", "COVID-19", [], ["Global"]),
        ("Chapare haemorrhagic fever- the Plurinational State of Bolivia", "Chapare haemorrhagic fever", ["BO"], []),
        ("Dengue – Iran (Islamic Republic of)", "Dengue", ["IR"], []),
        ("Chikungunya - La Réunion and Mayotte", "Chikungunya", ["RE", "YT"], []),
        ("Marburg virus disease - The Republic of Rwanda", "Marburg virus disease", ["RW"], []),
        ("Yellow fever - WHO African Region", "Yellow fever", [], ["WHO African Region"]),
        ("Rift Valley fever- Mauritania and Senegal", "Rift Valley fever", ["MR", "SN"], []),
        ("Yellow fever- East, West and Central Africa region", "Yellow fever", [], ["East, West and Central Africa"]),
    ]

    def test_real_titles(self):
        for title, disease, ccs, regions in self.CASES:
            d, place = places.split_title(title)
            got, rg, _ = places.countries_in(place or "")
            self.assertEqual(d, disease, title)
            self.assertEqual(got, ccs, title)
            self.assertEqual(rg, regions, title)

    def test_no_place(self):
        self.assertEqual(places.split_title("Avian Influenza A(H9N2)"), ("Avian Influenza A(H9N2)", None))

    def test_longest_name_wins(self):
        self.assertEqual(places.countries_in("Niger and Nigeria")[0], ["NE", "NG"])
        self.assertEqual(places.countries_in("South Sudan")[0], ["SS"])
        self.assertEqual(places.countries_in("Guinea-Bissau")[0], ["GW"])

    def test_territory_point(self):
        self.assertIsNotNone(places.point("RE"))


class Baseline(unittest.TestCase):
    def test_poisson_tail(self):
        self.assertEqual(ifrc.poisson_tail(0, 1.0), 1.0)
        self.assertAlmostEqual(ifrc.poisson_tail(1, 1.0), 1 - 0.36787944, places=6)
        self.assertLess(ifrc.poisson_tail(5, 0.3), 0.001)

    def test_recent_not_in_baseline(self):
        today = date(2026, 11, 16)
        hist = [{"country": "XX", "start_date": "2026-11-01"}, {"country": "XX", "start_date": "2026-10-01"},
                {"country": "XX", "start_date": "2020-01-01"}]
        ctx = ifrc.place_context(hist, today)["XX"]
        self.assertEqual(ctx["appeals_last_90_days"], 2)
        self.assertEqual(ctx["appeals_in_baseline"], 1)


class Iso(unittest.TestCase):
    def test_codes(self):
        self.assertEqual(iso.a2("hti"), "HT")
        self.assertEqual(iso.a2("XKX"), "XK")
        self.assertIsNone(iso.a2("wld"))
        self.assertEqual(len(set(iso.ALPHA3.values())), len(iso.ALPHA3))


class HapiNeeds(unittest.TestCase):
    def test_total_preferred(self):
        rows = [{"location_code": "MMR", "reference_period_start": "2025-01-01T00:00:00", "sector_code": "Intersectoral",
                 "admin_level": 0, "category": c, "population_status": "INN", "population": n, "resource_hdx_id": "r"}
                for c, n in (("", 1957173), ("total", 19902649))]
        self.assertEqual(hapi.needs_by_country(rows)[("MM", 2025)]["people_in_need"], 19902649)

    def test_licence_gate(self):
        fund = json.loads((FIX / "hapi_funding.json").read_text(encoding="utf-8"))["data"]
        res = json.loads((FIX / "hapi_resources.json").read_text(encoding="utf-8"))["data"]
        recs, extra = hapi.build(fund, [], res, {}, date(2026, 11, 16))   # no licence read: nothing published
        self.assertEqual(recs, [])
        self.assertGreater(extra["left_out"]["licence"], 0)
        recs, _ = hapi.build(fund, [], res, {r["dataset_hdx_stub"]: "cc-by-igo" for r in res}, date(2026, 11, 16))
        self.assertTrue(recs)
        self.assertTrue(all(r["appeal_code"] != hapi.NOT_SPECIFIED for r in recs))


class Thresholds(unittest.TestCase):
    GEN = "2026-11-16T12:00:00Z"   # window starts 2026-08-18

    def pc(self, n, p):
        return {"appeals_last_90_days": n, "tail_probability": p, "mean_per_90_days": 0.3,
                "baseline_window": "2016-11-16 to 2026-08-17", "appeals_in_baseline": 12}

    def test_ind1(self):
        r = {"country": "XX", "start_date": "2026-10-01", "place_context": self.pc(2, 0.005)}
        self.assertEqual(feed.rule("ifrc", r, self.GEN)["indicator"], "RL-IND-1")
        self.assertIsNone(feed.rule("ifrc", {**r, "place_context": self.pc(1, 0.0001)}, self.GEN))  # one appeal
        self.assertIsNone(feed.rule("ifrc", {**r, "place_context": self.pc(3, 0.01)}, self.GEN))    # not below 1%
        self.assertIsNone(feed.rule("ifrc", {**r, "start_date": "2026-08-17"}, self.GEN))           # before window
        self.assertIsNotNone(feed.rule("ifrc", {**r, "start_date": "2026-08-18"}, self.GEN))
        self.assertIsNone(feed.rule("ifrc", {**r, "place_context": None}, self.GEN))

    def test_ind2(self):
        self.assertEqual(feed.rule("who", {"prior_notices_730_days": {"XX": 0, "YY": 3}}, self.GEN)["countries"],
                         ["XX"])
        self.assertIsNone(feed.rule("who", {"prior_notices_730_days": {"XX": 1}}, self.GEN))
        self.assertIsNone(feed.rule("who", {"prior_notices_730_days": None}, self.GEN))  # read too short
        self.assertIsNone(feed.rule("who", {"prior_notices_730_days": {}}, self.GEN))

    def test_ind3(self):
        r = {"country": "XX", "year": 2026, "needs": {"people_in_need": 125, "people_in_need_prior_year": 100}}
        self.assertEqual(feed.rule("hapi", r, self.GEN)["indicator"], "RL-IND-3")
        self.assertIsNone(feed.rule("hapi", {**r, "needs": {"people_in_need": 124, "people_in_need_prior_year": 100}},
                                    self.GEN))
        self.assertIsNone(feed.rule("hapi", {**r, "needs": {"people_in_need": 500, "people_in_need_prior_year": None}},
                                    self.GEN))
        self.assertIsNone(feed.rule("hapi", {**r, "needs": None}, self.GEN))

    def test_ind4(self):
        rep = reliefweb.attention(11, 18)       # 11 against 1.5 a week
        r = {"record": "country", "country": "XX", "reports": rep}
        self.assertEqual(feed.rule("reliefweb", r, self.GEN)["indicator"], "RL-IND-4")
        self.assertIsNone(feed.rule("reliefweb", {**r, "reports": reliefweb.attention(9, 0)}, self.GEN))   # under 10
        self.assertIsNone(feed.rule("reliefweb", {**r, "reports": reliefweb.attention(12, 120)}, self.GEN))  # usual
        self.assertIsNotNone(feed.rule("reliefweb", {**r, "reports": reliefweb.attention(10, 0)}, self.GEN))  # new


class Pipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        for part in ("doctrine", "site_src"):
            shutil.copytree(ROOT / part, self.tmp / part)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_once(self, g=getter, keys=KEYS):
        snap = cli.collect(self.tmp, getter=g, now=NOW, keys=keys)
        cli.build_site(self.tmp)
        return snap

    def test_collect_build_check(self):
        snap = self.run_once()
        self.assertEqual({k: v["status"] for k, v in snap["lanes"].items()},
                         {"ifrc": "ok", "who": "ok", "hapi": "ok", "reliefweb": "ok"})
        self.assertEqual(cli.check_all(self.tmp), [])
        doc = json.loads((self.tmp / "site" / "data" / "feed.geojson").read_text(encoding="utf-8"))
        regs = registers.ids(self.tmp / "doctrine")
        self.assertTrue(doc["features"])
        for f in doc["features"]:
            errs = [m for _, sev, m in contract.check(f, regs) if sev == "error"]
            self.assertEqual(errs, [], f["properties"]["id"])
        self.assertEqual(set(doc["health"]), {"ifrc-go-appeals", "who-don", "hdx-hapi", "reliefweb-api"})
        lanes = {f["properties"]["id"].split("-")[1] for f in doc["features"]}
        self.assertEqual(lanes, {"IFRC", "WHO", "HAPI", "RW", "RWC"})
        # The recorded week has Rwanda at 11 reports against 1.5 a week: an RL-IND-4 country item.
        rwc = [f["properties"] for f in doc["features"] if f["properties"]["id"].startswith("RL-RWC-")]
        self.assertTrue(rwc and all(p["tier"] == "anomaly" for p in rwc))
        self.assertEqual(snap["extra"]["hapi"]["licences"]["global-hpc-hno"]["read"], "live")

    def test_keys_never_recorded(self):
        snap = self.run_once()
        data = self.tmp / "data"
        recorded = (data / "raw" / "index.jsonl").read_text(encoding="utf-8") + (data / "snapshot.json").read_text(
            encoding="utf-8") + "".join(p.read_text(encoding="utf-8") for p in (self.tmp / "site" / "data").glob("*"))
        for k in KEYS.values():
            self.assertNotIn(k, recorded)
        self.assertTrue(any("api.reliefweb.int" in u for u in SEEN))
        self.assertEqual(cli.terms_scan(list((self.tmp / "site" / "data").glob("*")), keys=KEYS), [])
        self.assertTrue(snap["lanes"]["reliefweb"]["fetches"])

    def test_key_scrubbed_from_errors(self):
        snap = self.run_once(g=leaky)
        self.assertEqual(snap["lanes"]["reliefweb"]["status"], "failed")
        self.assertNotIn(KEYS["RELIEFWEB_APPNAME"], json.dumps(snap))
        self.assertIn("<key>", snap["lanes"]["reliefweb"]["error"])

    def test_missing_key_fails_only_that_lane(self):
        snap = self.run_once(keys={})
        st = {k: v["status"] for k, v in snap["lanes"].items()}
        self.assertEqual(st, {"ifrc": "ok", "who": "ok", "hapi": "failed", "reliefweb": "failed"})
        self.assertIn("not set", snap["lanes"]["reliefweb"]["error"])
        self.assertEqual(cli.check_all(self.tmp), [])

    def test_licence_read_falls_back_to_recorded(self):
        snap = self.run_once(g=catalogue_down)
        self.assertEqual(snap["lanes"]["hapi"]["status"], "ok")
        self.assertTrue(all(v["read"].startswith("recorded") for v in snap["extra"]["hapi"]["licences"].values()))

    def test_anomaly_items_pass_contract_and_check(self):
        snap = self.run_once()
        gen = snap["generated_at"]
        ifrc_recent = [r for r in snap["records"]["ifrc"] if r["start_date"] >= feed.recent_from(gen)
                       and not r.get("past_end_date") and r.get("place_context")]
        self.assertTrue(ifrc_recent, "fixtures need an appeal in the 90-day window")
        target = ifrc_recent[0]
        target["place_context"] = {**target["place_context"], "appeals_last_90_days": 3, "tail_probability": 0.002}
        who = [r for r in snap["records"]["who"] if r.get("prior_notices_730_days")]
        if who:
            who[0]["prior_notices_730_days"] = {cc: 0 for cc in who[0]["prior_notices_730_days"]}
        plan = next(r for r in snap["records"]["hapi"] if r.get("needs"))
        plan["needs"] = {**plan["needs"], "people_in_need": 200, "people_in_need_prior_year": 100}
        dis = snap["records"]["reliefweb"][0]
        dis["reports"] = reliefweb.attention(30, 12)
        cli.build_site(self.tmp, snapshot=snap)
        self.assertEqual(cli.check_all(self.tmp), [])
        doc = json.loads((self.tmp / "site" / "data" / "feed.geojson").read_text(encoding="utf-8"))
        regs = registers.ids(self.tmp / "doctrine")
        anomalies = [f for f in doc["features"] if f["properties"]["tier"] == "anomaly"]
        for rec in (target, plan, dis):
            self.assertTrue(any(f["properties"]["id"] == feed.item_id(rec["key"]) for f in anomalies), rec["key"])
        for f in anomalies:
            self.assertIn("baseline_ref", f["properties"])
            self.assertIn("nusual", f["properties"]["summary"])
            self.assertEqual([m for _, sev, m in contract.check(f, regs) if sev == "error"], [])
        # check fails a tier that disagrees with the thresholds.
        doc["features"][-1]["properties"]["tier"] = (
            "routine" if doc["features"][-1]["properties"]["tier"] == "anomaly" else "anomaly")
        (self.tmp / "site" / "data" / "feed.geojson").write_text(json.dumps(doc), encoding="utf-8")
        self.assertTrue(any("does not match" in e for e in cli.check_all(self.tmp)))

    def test_no_who_body_text_published(self):
        self.run_once()
        for p in (self.tmp / "site" / "data").glob("*"):
            txt = p.read_text(encoding="utf-8")
            self.assertNotIn("fixture: WHO notice text removed", txt, p.name)
            self.assertNotIn("paraeid", txt, p.name)
            self.assertNotIn("fixture: ReliefWeb", txt, p.name)   # ReliefWeb's disaster names never copied

    def test_terms_scan_catches_body(self):
        p = self.tmp / "bad.geojson"
        p.write_text('{"Overview": "<p paraeid=\\"x\\">t</p>"}', encoding="utf-8")
        self.assertTrue(cli.terms_scan([p]))
        for bad in ('{"description": "x"}', '{"ipc_phase": "3"}', '{"u": "https://reliefweb.int/disaster/x?appname=y"}',
                    '{"t": "' + KEYS["RELIEFWEB_APPNAME"] + '"}', '{"t": "[fixture: ReliefWeb name removed]"}'):
            p.write_text(bad, encoding="utf-8")
            self.assertTrue(cli.terms_scan([p], keys=KEYS), bad)

    def test_failed_lane_keeps_last_good_copy(self):
        first = self.run_once()
        second = cli.collect(self.tmp, getter=failing, now="2026-11-16T08:00:00Z", keys=KEYS)
        for lane in cli.LANES:
            st = second["lanes"][lane]
            self.assertEqual(st["status"], "failed")
            self.assertTrue(st["from_previous"])
            self.assertEqual(len(second["records"][lane]), len(first["records"][lane]))
            self.assertEqual(st["failures"], 1)
        cli.build_site(self.tmp)
        doc = json.loads((self.tmp / "site" / "data" / "feed.geojson").read_text(encoding="utf-8"))
        self.assertEqual({v["state"] for v in doc["health"].values()}, {"failing"})

    def test_no_made_up_data(self):
        snap = cli.collect(self.tmp, getter=failing, now=NOW, keys=KEYS)
        self.assertEqual(sum(len(v) for v in snap["records"].values()), 0)

    def test_who_lane_published_window(self):
        vals = json.loads((FIX / "who_p0.json").read_text(encoding="utf-8"))["value"]
        recs, extra = who_don.build(vals, date(2026, 11, 16))
        self.assertTrue(all(r["published_day"] >= "2025-11-16" for r in recs))
        self.assertEqual(extra["places_parsed"], extra["places_stated"])

    def test_ids_stable(self):
        self.assertEqual(feed.item_id("ifrc:8439"), feed.item_id("ifrc:8439"))
        self.assertTrue(feed.item_id("who:2026-DON626").startswith("RL-WHO-"))


if __name__ == "__main__":
    unittest.main()
