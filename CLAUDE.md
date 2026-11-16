# Relief

Humanitarian response: roadmap step 7 and the top unbuilt slice in the suite's ideas file `_ideas/new-programs.md`, beside this folder (rank 2).
Tom, 15 Nov 2026: "Yes, start it" as its own program, not a Temper tab; named **Relief** the same evening. Program
id `relief`, item prefix `RL`, feed `tic-feed/2`, method `relief-0.1`. Groundwork:
`_ideas/drafts/2026-10-31-humanitarian-step7.md`. Planned address `relief.theintelligence.company` (`feed.SITE`).

## State, 15 Nov 2026, about 9 PM CST: built locally, not live

- No git repo, no GitHub repo, no Pages project, no DNS, no hub or COP listing. Each needs Tom's yes. D: is the only
  copy until there is a repo. The repo can be public from day one (fixtures are cut down on purpose), which keeps it
  off the private-repo Actions minutes. Run the privacy audit before the first push
  (`../_inventory/privacy-audit-2026-11-08/`): keep absolute local paths out of this file; the house-bar files
  (`site_src/tic-*.js`, `tic-nav.css`) carry the hub's local path in their headers, as they do on every public site.
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
1. `git init` and a first commit; a public repo `metacog-osint/relief` after the privacy audit; Pages project
   `relief` and the Squarespace CNAME for `relief.theintelligence.company`; `CLOUDFLARE_PAGES_TOKEN` and
   `CLOUDFLARE_ACCOUNT_ID` (Tom sets them). The workflow `.github/workflows/update.yml` is written, not run.
2. tic-dispatch entry in the hub's `dispatch/dispatch.js`; registry row `humanitarian` -> `relief`, live, in
   tic-doctrine; hub listing and house bar; COP layer (Society family colour).
3. HDX HAPI app identifier (encodes an email Tom chooses), IPC token (ipc@fao.org), ReliefWeb appname: the next lanes.
4. Thresholds for RL-IND-1 and RL-IND-2.
