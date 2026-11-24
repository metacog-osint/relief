# Method: Relief, relief-0.3

## What it measures
Four publishers' own records, read each run from their public APIs (the last two with a key):

- **IFRC appeals** (IFRC GO). Every Emergency Appeal and DREF allocation the IFRC marks Active, plus any appeal
  that started in the last 90 days: hazard, country, amounts requested and funded (Swiss francs, as IFRC states
  them), people targeted, start and end dates, and a link to the IFRC emergency page.
- **WHO outbreak notices** (Disease Outbreak News). Every notice WHO published in the last 365 days: the disease
  and place read from WHO's title, the countries and WHO regions named, the date and a link.

- **UN-coordinated plans** (OCHA's Financial Tracking Service, through the HDX Humanitarian API). Each plan or
  appeal for each country this year (response plans, flash appeals, regional plans): what it requires and the
  funding reported against it, in US dollars, with last year's plan of the same type for that country. FTS's "Not
  specified" rows (money outside any plan) are counted, not published. On the country's own plan (its response plan,
  else a flash appeal, never a regional plan), the intersectoral people in need and targeted from OCHA's
  Humanitarian Programme Cycle, against last year's plan.
- **ReliefWeb disasters** (ReliefWeb API). Every disaster ReliefWeb marks ongoing or alert: type, countries, GLIDE
  number, status, event date and a link, with the number of reports ReliefWeb posted on it in the last 7 days and
  its average per week over the 12 weeks before. The same count for each country as a report's main country is
  on the page; a country is a feed item only when its count meets RL-IND-4.

Each item is the publisher's report (kind observation, status reported, source grade A2); a ReliefWeb country count
is Relief's own count of ReliefWeb's posts (status assessed). Nothing here is a
judgment, a probability or a warning. An item is tier anomaly when it meets RL-IND-1 or RL-IND-2 below: unusual
for that place against its own past, still a measurement.

## How unusual for this place
- **Appeals.** For each country, the number of IFRC appeals that started in the last 90 days, against that
  country's own average per 90 days over the ten years before the window (`place_context`). The window's own
  appeals never count toward the baseline. The Poisson tail probability of at least that many is published with
  it. **RL-IND-1** (set 16 Nov 2026): an appeal that started in the last 90 days is tier anomaly when its
  country has at least 2 appeals in those 90 days and the tail probability is below 0.01. Older appeals in the
  same country stay routine: the count is about what started recently.
- **Outbreak notices.** For each country a notice names, how many earlier WHO notices named it in the two years
  before (`prior_notices_730_days`). **RL-IND-2** (set 16 Nov 2026): a notice naming a country with no WHO
  notice in the two years before is tier anomaly. It is left unset when WHO's read does not reach back the whole
  two years before the notice.
- **Plans.** For each country's own plan, the intersectoral people in need against last year's plan. HPC states the
  national total as category "total" (2025) or "" (2026); "total" is used where both exist, because in the 2025
  data "" is not always the total (Myanmar 2025: 1,957,173 against 19,902,649). **RL-IND-3** (set 18 Nov 2026): a
  plan whose people in need is at least 25% above last year's plan for that country is tier anomaly. Plans change
  scope between years (the 2026 cycle narrowed many), so only rises are marked.
- **ReliefWeb reports.** For each current disaster and each country, the reports posted in the last 7 days against
  the mean per week over the 12 weeks before (Poisson tail probability published). **RL-IND-4** (set 18 Nov 2026):
  at least 10 reports in 7 days and a tail probability below 0.01 is tier anomaly. A new disaster with no reports
  before has a mean of 0, so 10 reports in its first week meet it.

## What it cannot show
- An IFRC appeal shows where the Red Cross and Red Crescent asked for money. Crises the ICRC leads (most armed
  conflicts), or the UN or a government leads, may have no IFRC appeal. No appeal does not mean no need.
- A DREF allocation is normally funded in full when approved, so its funded share says little. An Emergency
  Appeal's funded share is the measure of response.
- IFRC keeps many appeals Active long after their end date (205 of 366 on 16 Nov 2026; the oldest started in
  2012). The feed, the totals and the funding chart count **current** appeals only (Active, end date not
  passed, or started in the last 90 days). The page lists the others too, marked "passed", behind a filter.
- FTS counts the funding reported to it against a plan. Money given outside the plan, or not reported, is not
  counted, so a low funded share can understate what reached a response (RL-ASM-5).
- A count of ReliefWeb reports measures reporting attention by ReliefWeb's content partners, not need or severity
  (RL-ASM-6). Reports with no single main country (ReliefWeb's "World") are counted apart.
- A WHO notice dates WHO's publication, often weeks after the member state notified WHO. The notice text is not
  kept, under WHO's terms, so the notification date is on WHO's page only.

## Terms
- IFRC GO: non-commercial use such as research; maps, charts and analyses allowed; the data bank is not copied or
  redistributed. The ten-year read is used for counts only; only active and recent appeals are published.
  The repository's history keeps, for each appeal read, its id, a hash of the record and IFRC's link, and counts per
  country and start year; the records themselves are kept in a private archive, not here.
- WHO: extracts for research with acknowledgement, not for commercial use; substantial portions need written
  permission. Only the title, date, place and link are published. The check fails the build if any notice body
  field reaches the site.
- HDX HAPI: HAPI's terms set no data licence of their own; each HDX dataset's licence governs. The funding (OCHA FTS)
  and needs (OCHA HPC) datasets are CC BY-IGO 3.0. Each dataset's licence is read from HDX's catalogue every run, and
  a row is published only when it is an open licence; if the catalogue cannot be read, the licence recorded on 18
  Nov 2026 is used and the snapshot says so. The app identifier is sent as a header and never recorded.
- ReliefWeb: personal, non-commercial use, with no right to redistribute, compile or create derivative works. Only
  counts, ids (ReliefWeb id, GLIDE), types, countries, status, dates and links are published, with titles Relief
  writes from them; never ReliefWeb's disaster names or descriptions, or any report's text. The appname is added to
  the request only and never recorded; ReliefWeb echoes it in its replies, so the raw copies (never cached or
  published) hold it and the test fixtures drop those fields.
- Not read: IPC food-security phases (HDX lists them as public domain, while IPC's own terms give CC BY-NC-SA 3.0
  IGO and forbid any military use: held for Tom's decision), IOM DTM displacement (no redistribution) and ACLED
  conflict events (ACLED's own terms). The check fails the build on any IPC or DTM field.

## Gaps and no-data
A lane that fails keeps its last good items, marked as such, and the feed's `health` block says the source is
failing. It never reads as "nothing new".

## Human review
None in this slice. The title parser's misses are counted every run (`coverage_fraction` 0 on the item).

## Next lanes (planned)
IPC phases (waits on Tom's decision on IPC's terms, then an API token); needs by first-level region from HAPI for a
map; UNHCR refugee figures and the INFORM risk index (both open licences, in HAPI). IOM DTM is link-only (its terms
forbid redistribution).

## Change log
- relief-0.1 (16 Nov 2026): first slice, IFRC appeals and WHO Disease Outbreak News.
- relief-0.2 (16 Nov 2026): thresholds for RL-IND-1 (p < 0.01, at least 2 appeals) and RL-IND-2 (first WHO
  notice for a country in two years) set by Tom; items that meet one are tier anomaly with a `baseline_ref`.
- relief-0.3 (18 Nov 2026): HDX HAPI lane (OCHA FTS plans and funding, OCHA HPC people in need) and ReliefWeb lane
  (current disasters, report counts); RL-IND-3 (people in need at least 25% above last year's plan) and RL-IND-4
  (at least 10 ReliefWeb reports in 7 days, p < 0.01 at the own 12-week mean) set by Tom.
