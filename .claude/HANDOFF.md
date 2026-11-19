# Relief handoff

Read on demand; `CLAUDE.md` holds the rules. Updated 19 Nov 2026.

## 18 Nov 2026: HAPI and ReliefWeb lanes built (relief-0.3)

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
  fixture holding a key value. Mask a key before slicing it in any diagnostic.
- HAPI's identifier goes in the `X-HDX-HAPI-APP-IDENTIFIER` header (checked 18 Nov: the header works, no
  parameter gives 403), so no HAPI URL carries it.
- COP reads the new items through its generic `RL-<LANE>-` rule (`tools/gate.py`); its routine label and the kit's
  suite description still say "IFRC appeals and WHO outbreak notices" (follow-up in those repos).

## 15 Nov 2026, about 10:45 PM CST: LIVE at https://relief.theintelligence.company/

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

## Now, 19 Nov 2026 (checked against git, Actions and the live site)

- 15 Nov prompt (`_ideas/drafts/2026-11-15-relief-next-session.md`) is fully done: git repo, privacy audit, public repo, Pages and
  DNS, suite wiring, thresholds RL-IND-1 to 4, HDX HAPI and ReliefWeb keys and lanes. Mark it replaced by this file.
- Shipped since: relief-0.3 lanes (`315be6b`), sections row and folds (`bc6e0a1`), AGPL-3.0 licence and policy (PRs 1, 2),
  private raw archive R2 (PR 3; needs `TIC_ARCHIVE_TOKEN` per suite issue 53).
- Live 19 Nov about 17:40 UTC: feed 340 items (IFRC 165, ReliefWeb disasters 85, HAPI 46, WHO 43, ReliefWeb country 1),
  8 anomaly; title "Relief: appeals, plans and outbreaks"; last scheduled run 15:53 UTC success.
- Left: (1) suite wording, stale in three repos: COP `config/programs.json` `routine_label`; kit `vocab/programs.json`
  Relief entry (status_note, `owns`, and `terms` still say "Relief code MIT"; code is AGPL-3.0); hub card text and
  sources list (IFRC and WHO only; hub push is Tom's yes). (2) IPC lane: held for Tom (no-military-use clause).
