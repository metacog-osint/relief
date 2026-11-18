# Relief

Humanitarian response: roadmap step 7 and the top unbuilt slice in the suite's ideas file `_ideas/new-programs.md`, beside this folder (rank 2).
Tom, 15 Nov 2026: "Yes, start it" as its own program, not a Temper tab; named **Relief** the same evening. Program
id `relief`, item prefix `RL`, feed `tic-feed/2`, method `relief-0.3` (HAPI and ReliefWeb lanes, 18 Nov 2026). Groundwork:
`_ideas/drafts/2026-10-31-humanitarian-step7.md`. Planned address `relief.theintelligence.company` (`feed.SITE`).

**Page layout (18 Nov 2026):** the hub's `tic-tabs.js` sections row (Unusual, Appeals, Outbreaks, Plans, Disasters,
Method) and `tic-fold.js` 1.0, the first site to use it: long tables and the funding bars show their first rows
and "Show all N" (`data-tic-fold`; find box on WHO, plans and ReliefWeb). Every appeal row is drawn; the fold
replaced the old 50-row "Show more". COP's `#<item id>` links open the row's group and fold.

## State, 18 Nov 2026: HAPI and ReliefWeb lanes built locally (relief-0.3), not yet pushed

- Tom, 18 Nov: "Yes, as proposed" to the scope below, RL-IND-3 and RL-IND-4 included. Built and checked locally:
  live collect IFRC 367, WHO 43, HAPI 46 plan rows (32 plans, 30 countries, 20 with needs), ReliefWeb 85
  disasters plus 1 country item; feed 338 items, 9 anomaly (Mozambique RL-IND-3 +80%; Rwanda RL-IND-4, 11 reports
  against 1.5 a week); check PASS; 25 tests pass with no keys in the environment. Page checked in the browser pane
  at 375 and 1280 px: no sideways scroll, no console errors.
- Terms read 18 Nov (sources in `doctrine/sources.json`): HAPI's terms set no data licence; per HDX dataset, FTS
  funding and HPC needs are CC BY-IGO 3.0; IOM DTM (idps) forbids redistribution; ACLED has its own terms; HDX
  lists IPC's dataset as CC0 while IPC's own terms are CC BY-NC-SA 3.0 IGO with a no-military-use clause, so IPC is
  held for Tom. ReliefWeb's terms: personal non-commercial use, no redistribution or compilation, so counts, ids,
  dates and links only. The API docs say the site terms govern the API; limits 1,000 calls a day and 1,000
  entries a call.
- ReliefWeb echoes the appname in each reply's top-level `href` and `links`. The raw copies in `data/raw/`
  (git-ignored, never cached) therefore hold it; `tests/make_fixtures.py` drops those fields and refuses to write a
  fixture holding a key value. 18 Nov: Claude's own diagnostic printed the first 12 characters of the appname into
  a local tool output (cut before masking); it never left the machine. Mask before slicing.
- HAPI's identifier goes in the `X-HDX-HAPI-APP-IDENTIFIER` header (checked 18 Nov: the header works, no
  parameter gives 403), so no HAPI URL carries it.
- COP reads the new items through its generic `RL-<LANE>-` rule (`tools/gate.py`); its routine label and the kit's
  suite description still say "IFRC appeals and WHO outbreak notices" (follow-up in those repos).

## State, 15 Nov 2026, about 10:45 PM CST: LIVE at https://relief.theintelligence.company/

- Public repo `metacog-osint/relief` (Tom's yes, 15 Nov evening), first commit `7272cf3`, pushed by sha after a
  privacy audit of the staged blobs and of a fresh mirror (`../_inventory/privacy-audit-2026-11-08/`). Hits were
  only the expected ones: the house-bar files (`site_src/tic-*.js`, `tic-nav.css`) carry the hub's local path in
  their headers, as on every public site, and the kit and house bar list the suite's programs. Keep absolute local
  paths out of this file. Fork PR approval set to `all_external_contributors`.
- The push ran `update.yml` (run 43798799602, success, 25 s): tests, live collect (IFRC 366, WHO 42), check PASS,
  history commit `f5f84fe` by relief-bot; deploy skipped because the Cloudflare secrets were not set yet. Pull before committing here: the bot commits `history/` each run.
- Pages project `relief` created 15 Nov about 10:00 PM CST with `wrangler pages project create relief
  --production-branch main --force` (without `--force`, wrangler 4.151 tries the new Workers-hosted Pages and fails
  on the Pages token's scope; `--force` is needed only at creation). Its address is **`relief-ad0.pages.dev`**
  (`relief.pages.dev` is someone else's site, ReliefViz). Repo variable `CLOUDFLARE_ACCOUNT_ID` copied from
  Undertow's (same, only account) and secret `CLOUDFLARE_PAGES_TOKEN` set by Tom. Run 43801627637 deployed:
  `https://relief-ad0.pages.dev/` serves "Relief: appeals and outbreaks" with a 203-item feed. Custom domain
  `relief.theintelligence.company` added to the project through the API (pending until DNS points at it).
- Squarespace CNAME `relief` -> `relief-ad0.pages.dev` (Tom changed it about 10:30 PM CST; it first pointed at
  `relief.pages.dev` from a wrong instruction of Claude's). 1.1.1.1 held the old answer (TTL 4 h) until purged with
  `curl -X POST "https://one.one.one.one/api/v1/purge?domain=relief.theintelligence.company&type=CNAME"`; the Pages
  domain went active 16 Nov 04:44 UTC. Checked: page 200 with valid TLS, title "Relief: appeals and outbreaks",
  feed 203 items, CSP header present, no console errors. No hub or COP listing yet.
- Suite wiring done 16 Nov 2026 about 12:50 AM CST (Tom: "Do the suite wiring"): tic-doctrine 0.5.9 (`relief`
  live, family Society, prefix `RL-WP`, fresh 12 h, stale 36 h) synced here; house bar v2.1 (Relief in the Programs
  menu, Human layer, beta) here, in COP and on the hub; COP layer pushed (`society` preset, earth brown `#8C510A`;
  COP's snapshot carried all 203 items at 06:48 UTC); hub listing, OE drawing and tic-dispatch job (:00 past 02,
  08, 14, 20 UTC) pushed, and the dispatch Worker redeployed. Tom deployed the hub site 16 Nov 06:58 UTC
  (checked: Relief card "Beta", Updated line, house bar v2.1, CSP allows Relief). Tom says he added `relief` to the
  `tic-dispatch` token; the first dispatched start (08:00 UTC 16 Nov) shows whether it took (a `workflow_dispatch`
  run in Relief's run list). Relief's own cron, 17 past every 6th hour, is the fallback.
- 16 Nov about 12:30 AM CST another session rewrote this repo's GitHub history (same content, new shas, plus its kit
  0.5.8 sync). The pre-rewrite local history is kept as branch `backup/pre-remote-rewrite-2026-11-16`.
- Live collect 16 Nov 2026 about 02:55 UTC: IFRC 366 appeals marked active (161 current, 205 past their end date),
  1,324 in the ten-year baseline; WHO 200 notices read, 42 in the last 12 months, all 200 titles with a place
  parsed. Feed 203 items, linter PASS, `check` PASS, 13 tests pass. Page checked in the browser pane at desktop and
  phone width before the rename (no sideways scroll, no console errors from the page's own code).
- Kit: tic-doctrine 0.5.7 vendored in `doctrine/kit/`.

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

## Next (each needs Tom)
0. Ship the HAPI and ReliefWeb lanes (commit + push, one yes), then check the run, the live feed and COP's next
   build. Then the suite wording (COP routine label, kit programs.json description, hub card) in those repos.
1. Dispatch token: done. Tom added Relief 16 Nov; dispatched runs every 6 h since 16 Nov 20:00 UTC (checked 18 Nov).
2. Keys for the next lanes (16 Nov 2026):
   - HDX HAPI: **set.** User env var and repo secret `HDX_HAPI_APP_IDENTIFIER` (Tom, 18:29 UTC; app name
     `TIC-Relief`, Tom's chosen email). Made with `GET https://hapi.humdata.org/api/v2/encode_app_identifier`
     (`application`, `email`; returns `encoded_app_identifier`, base64 of `application:email`, no account; API
     0.9.15). Checked: `/api/v2/metadata/location` answers with it. The HAPI lane can be built.
   - ReliefWeb: **approved** 18 Nov 01:55 UTC (ReliefWeb adjusted the name Tom sent to its naming standard; the
     approved name is in ReliefWeb's email to Tom). Checked: `api.reliefweb.int/v2/reports` answers with it. **Set**
     18 Nov 15:04 UTC as User env var and repo secret `RELIEFWEB_APPNAME`; keep the name itself out of this public
     repo (and out of logged URLs). The ReliefWeb lane can be built.
   - Building either lane: `update.yml` does not pass these secrets to `collect` yet (add them as step `env:`); a
     lane without its key must fail as a lane (last good copy kept), never break the run; check its terms (HDX
     dataset licences, ReliefWeb's terms) for free public non-commercial redistribution before publishing.
   - IPC: not requested yet. `api.ipcinfo.org` answers 401 "API key required". Request through the "Request access
     to the API" form on `ipcinfo.org/ipc-country-analysis/api/` (Cloudflare check; Tom's browser passes it). Terms
     read 16 Nov from Tom's saved copy of `API_TermsofUse-March2023.pdf` (IPC-CH API Terms of Use v2.0, March 2023):
     - Data licence **CC BY-NC-SA 3.0 IGO**: free public non-commercial redistribution allowed, so items need that
       licence carried (ShareAlike) and the credit "IPC CC BY-NC-SA 3.0 IGO", the data's last-updated date and a link
       to ipcinfo.org (plus cadreharmonise.org for Cadre Harmonisé data). Other commercial use needs IPC's consent.
     - "The IPC and the CH reject and forbid any use of their data for military purposes" (section II, repeated in
       IV.7); also "Do No Harm", and a caution on aggregating with other datasets. Tom's call how TIC's framing sits
       with this; raised with him 16 Nov.
     - Key confidential, non-transferable, one per implementation (Relief's workflow is one); use must match the
       purpose stated on the request form, and a change of purpose must be reported. IPC may name the requesting
       organisation and use its logo. Questions: ipc-tech-support@fao.org. API docs: docs.api.ipcinfo.org.
     - HDX HAPI's food-security data comes from IPC, so the same terms likely travel with it; read HAPI's licence
       fields per dataset before publishing IPC figures from either route.
