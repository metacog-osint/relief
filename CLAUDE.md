# Relief

Humanitarian response: roadmap step 7 and the top unbuilt slice in the suite's ideas file `_ideas/new-programs.md`, beside this folder (rank 2).
Tom, 15 Nov 2026: "Yes, start it" as its own program, not a Temper tab; named **Relief** the same evening. Program
id `relief`, item prefix `RL`, feed `tic-feed/2`, method `relief-0.1`. Groundwork:
`_ideas/drafts/2026-10-31-humanitarian-step7.md`. Planned address `relief.theintelligence.company` (`feed.SITE`).

## State, 15 Nov 2026, about 10:10 PM CST: deployed to Pages; custom domain waits on the CNAME

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
- Squarespace CNAME `relief` must target `relief-ad0.pages.dev`; it was set to `relief.pages.dev` from a wrong
  instruction of Claude's and gets HTTP 409 until changed. Squarespace asks for a Google re-verification before any
  DNS edit, which is Tom's to do. No hub or COP listing yet.
- The tic-doctrine registry row is still `id: humanitarian`, status planned. Renaming it to `relief` is a kit change
  (version bump, then `python tools/sync.py ../relief` from the kit's folder); the contract check does not need it.
- Live collect 16 Nov 2026 about 02:55 UTC: IFRC 366 appeals marked active (161 current, 205 past their end date),
  1,324 in the ten-year baseline; WHO 200 notices read, 42 in the last 12 months, all 200 titles with a place
  parsed. Feed 203 items, linter PASS, `check` PASS, 13 tests pass. Page checked in the browser pane at desktop and
  phone width before the rename (no sideways scroll, no console errors from the page's own code).
- Kit: tic-doctrine 0.5.7 vendored in `doctrine/kit/`.

## Commands

```bash
python tools/relief.py collect               # fetch both lanes into data/snapshot.json
python tools/relief.py collect --only who    # one lane; the other keeps its last copy
python tools/relief.py build                 # build site/ from data/snapshot.json
python tools/relief.py check                 # registers, contract per item, terms scan
python -m unittest discover -s tests         # offline tests on cut-down recorded replies
python tests/make_fixtures.py                # re-record fixtures from data/raw/ (after a collect)
python tools/serve.py 8783                   # site/ on http://127.0.0.1:8783; launch entry `relief-site` in `../.claude/launch.json`
python doctrine/kit/tic.py lint site/data/feed.geojson --doctrine doctrine
```

Standard library only. On Windows set `PYTHONIOENCODING=utf-8` when printing names (Panamá). The CLI
`tools/relief.py` shares its name with the package `relief/`, so the tests load it by path (importlib).

## Lanes

| Lane | Module | Source | Published |
|---|---|---|---|
| `ifrc` | `ifrc.py` | GO API `goadmin.ifrc.org/api/v2/appeal/`: `status=0` (active) and `start_date__gte` ten years back, 500 a page, following `next` | Current appeals (Active and end date not passed, or started in the last 90 days) in the feed; every active one on the page, marked "passed" |
| `who` | `who_don.py` | `www.who.int/api/news/diseaseoutbreaknews`, two pages of 100 (`$top` is capped at 100) | Notices from the last 365 days: title, disease and place read from the title, countries, regions, date, link |

`places.py` reads WHO's titles: the disease is before the first dash (or comma), the place after; country names
match longest first on word boundaries, with WHO's forms in `ALIASES` and French overseas departments given points
in `TERRITORY_POINTS`. A title whose place is not recognised gets `coverage_fraction` 0 and is listed in
`extra.who.unread_places`. Add a name to `ALIASES` and a test case when one appears.

## Measurements (no tier rule yet; Tom's call)
- `place_context` on each appeal: appeals started in the country in the last 90 days, the country's mean per 90 days
  over the ten years before (the window's own appeals excluded), and the Poisson tail probability. Indicator RL-IND-1
  proposes anomaly at p < 0.01 with at least 2 appeals. On 16 Nov the lowest was Panama, 2 against 0.30 (p 0.038).
- `prior_notices_730_days` on each WHO notice: WHO's notices naming each country in the two years before. RL-IND-2
  proposes "first in two years".
- Every item is tier routine, kind observation. `check` fails anything else.

## Hard rules
- **Terms.** IFRC GO: non-commercial, analyses allowed, no copying of the data bank (the ten-year read is counts
  only). WHO: extracts for research with acknowledgement, no substantial reproduction: never keep or publish notice
  body fields (`Overview`, `Epidemiology`, `Assessment`, `Advice`, `Response`, `FurtherInformation`, `Summary`).
  `check`'s terms scan fails the build on any of them, on WHO's `paraeid` markup, or on a URL outside the allowed
  publisher pages.
- `data/raw/` (full replies) is git-ignored and never cached or published. `tests/fixtures/` holds 60 active and
  120 baseline appeals and 60 WHO notices with every body field replaced by a marker.
- The page's CSP is `style-src 'self'`: set styles through the CSSOM (see the funding bars), never in markup.

## Next (each needs Tom)
1. Squarespace CNAME `relief` -> `relief-ad0.pages.dev`, then check `https://relief.theintelligence.company/`
   serves the page and feed and the Pages custom domain shows active.
2. tic-dispatch entry in the hub's `dispatch/dispatch.js`; registry row `humanitarian` -> `relief`, live, in
   tic-doctrine; hub listing and house bar; COP layer (Society family colour).
3. HDX HAPI app identifier (encodes an email Tom chooses), IPC token (ipc@fao.org), ReliefWeb appname: the next lanes.
4. Thresholds for RL-IND-1 and RL-IND-2.
