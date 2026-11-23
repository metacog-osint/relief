# Relief

Humanitarian response: roadmap step 7 and the top unbuilt slice in the suite's private planning notes (rank 2).
Tom, 15 Nov 2026: "Yes, start it" as its own program, not a Temper tab; named **Relief** the same evening. Program
id `relief`, item prefix `RL`, feed `tic-feed/2`, method `relief-0.3` (HAPI and ReliefWeb lanes, 18 Nov 2026). Groundwork:
the private planning notes. Planned address `relief.theintelligence.company` (`feed.SITE`).

**Page layout (18 Nov 2026):** the hub's `tic-tabs.js` sections row (Unusual, Appeals, Outbreaks, Plans, Disasters,
Method) and `tic-fold.js` 1.0, the first site to use it: long tables and the funding bars show their first rows
and "Show all N" (`data-tic-fold`; find box on WHO, plans and ReliefWeb). Every appeal row is drawn; the fold
replaced the old 50-row "Show more". COP's `#<item id>` links open the row's group and fold.

## State, 19 Nov 2026: live, relief-0.3 (HAPI and ReliefWeb lanes) shipped

Current state is in `.claude/HANDOFF.md` (read on demand): what is live, the 15 and 18 Nov history, terms notes, and
what is left. Live at https://relief.theintelligence.company/ (Pages project `relief`, address
`relief-ad0.pages.dev`); `update.yml` runs on a 6-hourly schedule and on `tic-dispatch` starts, and the bot commits
`history/` each run, so pull before committing.

## Commands

```bash
python tools/relief.py collect               # fetch both lanes into data/snapshot.json
python tools/relief.py collect --only who    # one or more lanes (ifrc who hapi reliefweb); the rest keep their last copy
python tools/relief.py build                 # build site/ from data/snapshot.json
python tools/relief.py check                 # registers, contract per item, terms scan
python -m unittest discover -s tests         # offline tests on cut-down recorded replies
python tests/make_fixtures.py --only hapi reliefweb   # re-record some lanes' fixtures from data/raw/ (after a collect)
python tools/serve.py 8783                   # site/ on http://127.0.0.1:8783; launch entry `relief-site` in `../.claude/launch.json`
python doctrine/kit/tic.py lint site/data/feed.geojson --doctrine doctrine
```

Standard library only. On Windows set `PYTHONIOENCODING=utf-8` when printing names (Panamá). The hapi and
reliefweb lanes read `HDX_HAPI_APP_IDENTIFIER` and `RELIEFWEB_APPNAME` from the environment; a session started
before Tom set them sees neither, so read them from the User scope in the same command, without printing them
(Bash: `export RELIEFWEB_APPNAME="$(powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('RELIEFWEB_APPNAME','User')" | tr -d '\r\n')"`). The CLI
`tools/relief.py` shares its name with the package `relief/`, so the tests load it by path (importlib).

## Lanes

| Lane | Module | Source | Published |
|---|---|---|---|
| `ifrc` | `ifrc.py` | GO API `goadmin.ifrc.org/api/v2/appeal/`: `status=0` (active) and `start_date__gte` ten years back, 500 a page, following `next` | Current appeals (Active and end date not passed, or started in the last 90 days) in the feed; every active one on the page, marked "passed" |
| `who` | `who_don.py` | `www.who.int/api/news/diseaseoutbreaknews`, two pages of 100 (`$top` is capped at 100) | Notices from the last 365 days: title, disease and place read from the title, countries, regions, date, link |
| `hapi` | `hapi.py` | HDX HAPI `coordination-context/funding` and `affected-people/humanitarian-needs` (admin 0, Intersectoral) from 1 Jan last year, `metadata/resource`; each dataset's licence from HDX `package_show` (recorded licence if HDX's bot check refuses). About 1 call a second | One record per plan per country this year (FTS "Not specified" rows left out), last year's plan of the same type, and on the country's own plan the people in need and targeted against last year |
| `reliefweb` | `reliefweb.py` | ReliefWeb `v2/disasters` (status ongoing or alert, one call) and two `v2/reports` facet calls (main country, disaster id) for the last 7 days and the 12 weeks before | Current disasters: type, countries, GLIDE, status, dates, link, report counts; a country item only when it meets RL-IND-4. No ReliefWeb name or text |

`places.py` reads WHO's titles: the disease is before the first dash (or comma), the place after; country names
match longest first on word boundaries, with WHO's forms in `ALIASES` and French overseas departments given points
in `TERRITORY_POINTS`. A title whose place is not recognised gets `coverage_fraction` 0 and is listed in
`extra.who.unread_places`. Add a name to `ALIASES` and a test case when one appears. `iso.py` maps the alpha-3
codes HAPI and ReliefWeb use to the contract's alpha-2 (all 239 kit countries reachable; XKX -> XK; "wld" -> none).

## Measurements and thresholds (RL-IND-1/2 set by Tom 16 Nov 2026, RL-IND-3/4 18 Nov 2026; method relief-0.3)
- `place_context` on each appeal: appeals started in the country in the last 90 days, the country's mean per 90 days
  over the ten years before (the window's own appeals excluded), and the Poisson tail probability. **RL-IND-1:** an
  appeal that started in the 90-day window is tier anomaly when its country has at least 2 appeals in the window
  and p < 0.01; older appeals in that country stay routine.
- `prior_notices_730_days` on each WHO notice: WHO's notices naming each country in the two years before (from
  WHO's titles; unset when the read does not reach back two years). **RL-IND-2:** any country at 0 makes the notice
  tier anomaly.
- `needs` on a country's own plan (HAPI): people in need and targeted, this year and last. HPC's national total is
  category "total" (2025) or "" (2026); "total" wins where both exist (Myanmar 2025 "" is 1,957,173, "total"
  19,902,649). **RL-IND-3:** people in need at least 25% above last year's plan is tier anomaly.
- `reports` on each ReliefWeb disaster and country: reports in the last 7 days, mean per week over the 12 weeks
  before, Poisson tail. **RL-IND-4:** at least 10 reports and p < 0.01 is tier anomaly.
- `feed.rule()` is the one statement of all four; `check` recomputes it from each item's fields and fails a tier that
  disagrees, or any kind but observation. Anomalies carry `baseline_ref`; no `indicator_id` (no warning problem, and
  the contract would then want a hypothesis). 16 Nov 15:40 UTC: 5 anomalies, all RL-IND-2 (Qatar MERS, France
  Shamonda, Kenya and Nigeria in the Bundibugyo Ebola notice, Russia, Italy H9N2); no appeal met RL-IND-1 (lowest
  Panama, 2 against 0.30, p 0.038).

## Hard rules
- **Terms.** HDX HAPI: publish a row only when its dataset's licence is open (`hapi.OPEN_LICENCES`); credit OCHA
  FTS / OCHA HPC and link CC BY-IGO 3.0. ReliefWeb: counts, ids, dates and links only, titles written by Relief;
  never ReliefWeb's `name`, `description`, `profile` or any report text, and never the appname anywhere (the terms
  scan fails on `appname=`, `app_identifier=`, either key's value when set, ReliefWeb text fields, IPC and DTM
  fields, and the ReliefWeb fixture marker; `update.yml` passes both secrets to the checks so the scan can look).
  IFRC GO: non-commercial, analyses allowed, no copying of the data bank (the ten-year read is counts
  only). WHO: extracts for research with acknowledgement, no substantial reproduction: never keep or publish notice
  body fields (`Overview`, `Epidemiology`, `Assessment`, `Advice`, `Response`, `FurtherInformation`, `Summary`).
  `check`'s terms scan fails the build on any of them, on WHO's `paraeid` markup, or on a URL outside the allowed
  publisher pages.
- `data/raw/` (full replies) is git-ignored and never cached or published. `tests/fixtures/` holds 60 active and
  120 baseline appeals and 60 WHO notices with every body field replaced by a marker; HAPI rows for ten countries
  with the three resources they cite and each dataset's licence id; 20 ReliefWeb disasters with the name replaced
  by a marker, and the two report-count replies, without ReliefWeb's `href`/`links` echo.
- The page's CSP is `style-src 'self'`: set styles through the CSSOM (see the funding bars), never in markup.

## Next
See `.claude/HANDOFF.md`. Open: suite wording (COP routine label, kit `programs.json` entry, hub card) and IPC
(held for Tom; the use-for-military-purposes clause in IPC's terms).
