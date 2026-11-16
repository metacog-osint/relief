# Relief

Part of The Intelligence Company's suite of public monitoring programs. It reads two publishers' own records:

- **IFRC appeals** (IFRC GO): Emergency Appeals and DREF allocations, with how much is funded and how unusual
  each country's count of new appeals is against its own ten-year record.
- **WHO Disease Outbreak News**: the notices WHO published in the last 12 months, with the disease and place read
  from WHO's title and a link to the notice.

Measurements and publishers' records only: no probability, no warning. An IFRC appeal shows where the IFRC asked
for money, not every place in need. Method: [`doctrine/method.md`](doctrine/method.md). Feed: `tic-feed/2`
GeoJSON at `data/feed.geojson`.

```bash
python tools/relief.py collect && python tools/relief.py build && python tools/relief.py check
python -m unittest discover -s tests
```

Python 3.12, standard library only. No source needs a key.

Sources and terms: IFRC GO (non-commercial use with credit; the data bank is not redistributed) and WHO (extracts
for research with acknowledgement; no notice text is kept). The feed's own text is CC BY 4.0; a licence for the
code is not chosen yet. The vendored doctrine kit keeps its own licence (`doctrine/kit/LICENSE`).
