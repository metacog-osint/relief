# Relief

Part of The Intelligence Company's suite of public monitoring programs. It reads four publishers' own records:

- **IFRC appeals** (IFRC GO): Emergency Appeals and DREF allocations, with how much is funded and how unusual
  each country's count of new appeals is against its own ten-year record.
- **WHO Disease Outbreak News**: the notices WHO published in the last 12 months, with the disease and place read
  from WHO's title and a link to the notice.
- **UN-coordinated plans** (OCHA FTS and OCHA's Humanitarian Programme Cycle, through the HDX Humanitarian API):
  each plan's requirements and reported funding for each country this year, and the people in need it counts,
  against last year's plan.
- **ReliefWeb**: the disasters ReliefWeb currently tracks, and how many reports it posted on each disaster and
  each country in the last 7 days against the 12 weeks before.

Measurements and publishers' records only: no probability, no warning. An IFRC appeal shows where the IFRC asked
for money, not every place in need. Method: [`doctrine/method.md`](doctrine/method.md). Feed: `tic-feed/2`
GeoJSON at `data/feed.geojson`.

```bash
python tools/relief.py collect && python tools/relief.py build && python tools/relief.py check
python -m unittest discover -s tests
```

Python 3.12, standard library only. Two lanes need a key in the environment: `HDX_HAPI_APP_IDENTIFIER` (HDX HAPI)
and `RELIEFWEB_APPNAME` (ReliefWeb's pre-approved appname). Without one, that lane fails and the others run.

Sources and terms: IFRC GO (non-commercial use with credit; the data bank is not redistributed), WHO (extracts
for research with acknowledgement; no notice text is kept), OCHA FTS and HPC via HDX HAPI (CC BY-IGO 3.0, each
dataset's licence read every run) and ReliefWeb (no redistribution: counts, ids, dates and links only). IPC
food-security figures are not read while IPC's terms are under review. The feed's own text is CC BY 4.0; the code's licence is below.

## Licence

Copyright © 2026 Thomas Brummer, The Intelligence Company. Relief's code is licensed under the GNU Affero General Public License
v3.0 (`LICENSE`). Third-party and shared files keep their own licences, and data keeps its sources'
terms; both are listed in `NOTICE`.

## AI assistance

This repository is built with AI coding assistance (Anthropic's Claude Code). The Intelligence Company is responsible for everything published here.
