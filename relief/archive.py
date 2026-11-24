"""Retention archives: append-only jsonl files under history/ that keep what the live view drops.

    history/appeals-index.jsonl     one line per IFRC appeal Relief reads, new or changed: its id, when seen, a hash
                                    of the record and IFRC's link. No field of the record itself.
    history/appeals-counts.json     appeals read per country and start year (rewritten each run; git keeps versions)
    history/who-notices.jsonl       every WHO DON notice read (id, title, place, date, link: no body text)
    history/funding.jsonl           HAPI plan funding and needs, when a value changes
    history/reliefweb-counts.jsonl  ReliefWeb report counts per country and disaster, once per ISO week

Lines are only ever appended. A row is written when its id is new or its content hash differs from the id's last
line; an unchanged row writes nothing, so a repeated run adds no lines. The live feed and site are not touched.

IFRC appeals (24 Nov 2026): the public repo keeps counts and links only, as the terms line says. The full records
(every version, the ten-year read included) go to the PRIVATE archive, metacog-osint/tic-archive, lane
relief-appeals, as one append-only appeals.jsonl in the format the public history/appeals.jsonl had until then:
`run_full` appends to a restored copy and the workflow uploads it (tools/tic_archive.py). `run_full` decides from the
private file's own hashes, never from the public index, so a failed upload is made good by the next run. The old
public file is folded in line for line and removed by `retire_legacy` only once every line of it is in the private
file and the upload succeeded.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

# Fields that are derived from today's date or from other records, not seen at the source.
DERIVED = ("past_end_date", "place_context", "prior_notices_730_days", "prior_year_plan")


def content(rec: dict) -> dict:
    return {k: v for k, v in rec.items() if k not in DERIVED}


def digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                          ).hexdigest()[:16]


def last_hashes(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                out[row["id"]] = row["hash"]
    return out


def append_changed(path: Path, rows: list[tuple[str, dict]], seen_at: str) -> int:
    """Append (id, content) rows that are new or changed. Returns the number of lines written."""
    seen = last_hashes(path)
    lines = []
    for rid, body in rows:
        h = digest(body)
        if seen.get(rid) == h:
            continue
        seen[rid] = h
        lines.append(json.dumps({"id": rid, "seen_at": seen_at, "hash": h, "record": body},
                                sort_keys=True, ensure_ascii=False, separators=(",", ":")))
    if lines:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines) + "\n")
    return len(lines)


APPEALS_INDEX = "appeals-index.jsonl"
APPEALS_COUNTS = "appeals-counts.json"
APPEALS_FULL = "appeals.jsonl"      # the private file's name, and the public file's until 24 Nov 2026


def _rows(path: Path) -> list[tuple[str, dict]]:
    """(line as written, parsed row) for each line of a jsonl file; [] if absent."""
    if not path.exists():
        return []
    return [(ln, json.loads(ln)) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _append_lines(path: Path, lines: list[str]) -> int:
    if lines:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines) + "\n")
    return len(lines)


def index_line(rid: str, seen_at: str, h: str, url) -> str:
    return json.dumps({"id": rid, "seen_at": seen_at, "hash": h, "url": url},
                      sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def index_appeals(hist_dir: Path, rows: list[tuple[str, dict]], seen_at: str) -> int:
    """Append an index line for each appeal that is new or whose record changed. If the old public file is still in
    history/, its lines the index lacks are indexed first, with their own seen_at. Returns the lines written."""
    path = hist_dir / APPEALS_INDEX
    held = {(r["id"], r["hash"]) for _, r in _rows(path)}
    lines = []
    for _, r in _rows(hist_dir / APPEALS_FULL):
        if (r["id"], r["hash"]) not in held:
            held.add((r["id"], r["hash"]))
            lines.append(index_line(r["id"], r["seen_at"], r["hash"], (r.get("record") or {}).get("url")))
    _append_lines(path, lines)
    seen = last_hashes(path)
    new = []
    for rid, body in rows:
        h = digest(body)
        if seen.get(rid) != h:
            seen[rid] = h
            new.append(index_line(rid, seen_at, h, body.get("url")))
    return len(lines) + _append_lines(path, new)


def appeal_counts(records: list[dict], as_of: str) -> dict:
    by: dict[str, dict[str, int]] = {}
    for r in records:
        cc, year = r.get("country") or "none", (r.get("start_date") or "")[:4] or "none"
        by.setdefault(cc, {})
        by[cc][year] = by[cc].get(year, 0) + 1
    return {"as_of": as_of, "appeals": len(records),
            "what": "IFRC appeals Relief read this run (every Active one, and every one started in the last ten "
                    "years), counted by country (ISO alpha-2) and start year. Counts only: the records are not here.",
            "by_country_start_year": {cc: dict(sorted(v.items())) for cc, v in sorted(by.items())}}


def run_full(snap: dict, private_dir: Path, legacy: Path | None = None) -> dict[str, int]:
    """Bring the private copy of the full appeal records up to date. `private_dir` holds appeals.jsonl as restored
    from the private archive. Lines of the old public file (`legacy`) that it lacks are added first, as written; then
    every appeal of this run that is new or changed against the private file's own last hash."""
    path = private_dir / APPEALS_FULL
    n = {"legacy": 0, "appeals": 0}
    if legacy is not None and legacy.exists():
        held = {ln for ln, _ in _rows(path)}
        n["legacy"] = _append_lines(path, [ln for ln, _ in _rows(legacy) if ln not in held])
    if (snap.get("lanes") or {}).get("ifrc", {}).get("status") == "ok":
        rows = [(r["appeal_id"], content(r)) for r in (snap.get("archive") or {}).get("ifrc") or []]
        n["appeals"] = append_changed(path, rows, snap["generated_at"])
    return n


def retire_legacy(private_dir: Path, legacy: Path) -> int:
    """Remove the old public file, but only when every line of it is in the private file. Returns the lines it held
    (0 when it was already gone). Call it only after the private file was uploaded."""
    if not legacy.exists():
        return 0
    held = {ln for ln, _ in _rows(private_dir / APPEALS_FULL)}
    lines = [ln for ln, _ in _rows(legacy)]
    missing = sum(1 for ln in lines if ln not in held)
    if missing:
        raise RuntimeError(f"{missing} of {len(lines)} lines of the public file are not in the private copy; kept")
    legacy.unlink()
    return len(lines)


def funding_body(r: dict) -> dict:
    n = r.get("needs") or {}
    src = r.get("funding_source") or {}
    return {"appeal_code": r["appeal_code"], "appeal_name": r.get("appeal_name"), "appeal_type": r.get("appeal_type"),
            "country": r["country"], "year": r.get("year"), "period_start": r.get("period_start"),
            "period_end": r.get("period_end"), "requirements_usd": r.get("requirements_usd"),
            "funding_usd": r.get("funding_usd"), "funded_share": r.get("funded_share"),
            "people_in_need": n.get("people_in_need"), "people_targeted": n.get("people_targeted"),
            "needs_year": n.get("year"), "dataset": src.get("dataset"), "licence_id": src.get("licence_id")}


def counts_row(snap: dict) -> dict | None:
    rw = (snap.get("extra") or {}).get("reliefweb") or {}
    if not rw.get("countries"):
        return None
    t = datetime.fromisoformat(snap["generated_at"].replace("Z", "+00:00"))
    y, w, _ = t.isocalendar()
    dis = [{"disaster_id": r["disaster_id"], "reports_last_7_days": (r.get("reports") or {}).get("reports_last_7_days"),
            "reports_in_baseline": (r.get("reports") or {}).get("reports_in_baseline")}
           for r in (snap.get("records") or {}).get("reliefweb", []) if r.get("record") == "disaster"]
    ctr = [{"country": c["country"], "reports_last_7_days": c["reports_last_7_days"],
            "reports_in_baseline": c["reports_in_baseline"]} for c in rw["countries"]]
    return {"id": f"{y}-W{w:02d}", "window": rw.get("window"), "baseline_weeks": 12, "countries": ctr,
            "disasters": dis}


def run(snap: dict, hist_dir: Path) -> dict[str, int]:
    """Write the public archives from a collected snapshot. A lane that did not read fresh this run adds nothing.
    IFRC appeals: the index and the counts only; the records themselves go to the private archive (`run_full`)."""
    now = snap["generated_at"]
    arc = snap.get("archive") or {}

    def fresh(lane):
        return (snap.get("lanes") or {}).get(lane, {}).get("status") == "ok"

    n = {"appeals": 0, "who-notices": 0, "funding": 0, "reliefweb-counts": 0}
    if fresh("ifrc"):
        rows = [(r["appeal_id"], content(r)) for r in arc.get("ifrc") or []]
        n["appeals"] = index_appeals(hist_dir, rows, now)
        (hist_dir / APPEALS_COUNTS).write_text(
            json.dumps(appeal_counts(arc.get("ifrc") or [], now), sort_keys=True, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8", newline="\n")
    if fresh("who"):
        rows = [(r["key"], content(r)) for r in arc.get("who") or []]
        n["who-notices"] = append_changed(hist_dir / "who-notices.jsonl", rows, now)
    if fresh("hapi"):
        rows = [(f"{r['appeal_code']}:{r['country']}:{r.get('year')}", funding_body(r))
                for r in (snap.get("records") or {}).get("hapi", [])]
        n["funding"] = append_changed(hist_dir / "funding.jsonl", rows, now)
    if fresh("reliefweb"):
        row = counts_row(snap)
        p = hist_dir / "reliefweb-counts.jsonl"
        if row and row["id"] not in last_hashes(p):
            body = {k: v for k, v in row.items() if k != "id"}
            n["reliefweb-counts"] = append_changed(p, [(row["id"], body)], now)
    return n
