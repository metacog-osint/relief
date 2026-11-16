# Method: Relief, relief-0.1

## What it measures
Two publishers' own records, read each run from their public APIs with no key:

- **IFRC appeals** (IFRC GO). Every Emergency Appeal and DREF allocation the IFRC marks Active, plus any appeal
  that started in the last 90 days: hazard, country, amounts requested and funded (Swiss francs, as IFRC states
  them), people targeted, start and end dates, and a link to the IFRC emergency page.
- **WHO outbreak notices** (Disease Outbreak News). Every notice WHO published in the last 365 days: the disease
  and place read from WHO's title, the countries and WHO regions named, the date and a link.

Each item is the publisher's report (kind observation, status reported, source grade A2). Nothing here is a
judgment, a probability or a warning.

## How unusual for this place
- **Appeals.** For each country, the number of IFRC appeals that started in the last 90 days, against that
  country's own average per 90 days over the ten years before the window (`place_context`). The window's own
  appeals never count toward the baseline. The Poisson tail probability of at least that many is published with
  it. It is a measurement only: no tier rule is set on it yet (indicator RL-IND-1, proposed, waits for review).
- **Outbreak notices.** For each country a notice names, how many earlier WHO notices named it in the two years
  before (`prior_notices_730_days`). "First in two years" is a measurement (RL-IND-2, proposed).

## What it cannot show
- An IFRC appeal shows where the Red Cross and Red Crescent asked for money. Crises the ICRC leads (most armed
  conflicts), or the UN or a government leads, may have no IFRC appeal. No appeal does not mean no need.
- A DREF allocation is normally funded in full when approved, so its funded share says little. An Emergency
  Appeal's funded share is the measure of response.
- IFRC keeps many appeals Active long after their end date (205 of 366 on 16 Nov 2026; the oldest started in
  2012). The feed, the totals and the funding chart count **current** appeals only (Active, end date not
  passed, or started in the last 90 days). The page lists the others too, marked "passed", behind a filter.
- A WHO notice dates WHO's publication, often weeks after the member state notified WHO. The notice text is not
  kept, under WHO's terms, so the notification date is on WHO's page only.

## Terms
- IFRC GO: non-commercial use such as research; maps, charts and analyses allowed; the data bank is not copied or
  redistributed. The ten-year read is used for counts only; only active and recent appeals are published.
- WHO: extracts for research with acknowledgement, not for commercial use; substantial portions need written
  permission. Only the title, date, place and link are published. The check fails the build if any notice body
  field reaches the site.

## Gaps and no-data
A lane that fails keeps its last good items, marked as such, and the feed's `health` block says the source is
failing. It never reads as "nothing new".

## Human review
None in this slice. The title parser's misses are counted every run (`coverage_fraction` 0 on the item).

## Next lanes (planned)
HDX HAPI (needs, funding, food security and displacement by first-level region), IPC phases, ReliefWeb. Each
waits on an identifier or token that Tom requests. IOM DTM is link-only (its terms forbid redistribution).

## Change log
- relief-0.1 (16 Nov 2026): first slice, IFRC appeals and WHO Disease Outbreak News.
