"""Record small test fixtures from the raw copies of the last collect (data/raw/, git-ignored).

    python tests/make_fixtures.py

The fixtures are cut down on purpose, because the repository may be public and neither publisher allows bulk
reposting: 60 active and 120 baseline IFRC appeals (real records, `next` removed), and 60 WHO notices with every
body field replaced by a marker paragraph (titles, ids and dates are real). The marker keeps WHO's `paraeid`
attribute so the terms scan has something to catch.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "tests" / "fixtures"
BODY = ("Response", "FurtherInformation", "Summary", "Epidemiology", "Advice", "Assessment", "Overview")


def latest(source_id: str, needle: str) -> bytes:
    rows = [json.loads(line) for line in (RAW / "index.jsonl").read_text(encoding="utf-8").splitlines()]
    rows = [r for r in rows if r["source_id"] == source_id and needle in r["url"]]
    if not rows:
        raise SystemExit(f"no raw copy for {source_id} {needle}: run tools/relief.py collect first")
    sha = rows[-1]["sha256"][:12]
    return gzip.decompress((RAW / source_id / f"{sha}.json.gz").read_bytes())


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    active = json.loads(latest("ifrc-go-appeals", "status=0"))
    hist = json.loads(latest("ifrc-go-appeals", "start_date__gte"))
    a = active["results"][:60]
    h = hist["results"][:120]
    (OUT / "ifrc_active.json").write_text(json.dumps({"count": len(a), "next": None, "results": a}), encoding="utf-8")
    (OUT / "ifrc_history.json").write_text(json.dumps({"count": len(h), "next": None, "results": h}), encoding="utf-8")
    who = json.loads(latest("who-don", "skip=0").decode("utf-8"))
    vals = who["value"][:60]
    for v in vals:
        for f in BODY:
            if f in v:
                v[f] = '<p paraeid="{fixture}">[fixture: WHO notice text removed]</p>'
    (OUT / "who_p0.json").write_text(json.dumps({"value": vals}, ensure_ascii=False), encoding="utf-8")
    print(f"fixtures: {len(a)} active, {len(h)} baseline appeals, {len(vals)} WHO notices")


if __name__ == "__main__":
    main()
