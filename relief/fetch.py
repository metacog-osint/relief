"""Fetch a source, hash it, and keep the raw copy before anything is derived from it.

Collection order (suite rule): fetch, hash, store the raw copy, record the times, then derive.
Raw copies go under data/raw/<source>/<sha12>.<ext> (git-ignored), and every fetch adds one line
to data/raw/index.jsonl, so a later reader can tell which bytes a fact came from. Copied from Undertow (which copied Headwind).

The raw copies hold the publishers' full replies. They stay on disk (never cached or
published): only what the lanes derive reaches site/, because neither publisher allows bulk reposting.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = os.environ.get("RELIEF_UA", "Mozilla/5.0 (compatible; research-collector/1.0)")


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get(url: str, timeout: int = 60, headers: dict | None = None) -> bytes:
    h = {"User-Agent": UA, "Accept": "*/*"}
    h.update(headers or {})
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch(source_id: str, url: str, raw_dir: Path | None, ext: str, timeout: int = 60, getter=None,
          gz: bool = False, headers: dict | None = None, secret_query: dict | None = None) -> tuple[bytes, dict]:
    """Return (bytes, record). The record carries the URL, SHA-256, size and fetch time.

    headers (for example an Authorization header) and secret_query (for example ReliefWeb's appname) are added to
    the request only; they are never recorded, so the record's URL is the one without them. A test getter gets
    that URL too. gz stores the raw copy gzipped; the hash and size are of the bytes as fetched."""
    if getter is not None:
        body = getter(url, timeout)
    else:
        full = url
        if secret_query:
            full += ("&" if "?" in url else "?") + urllib.parse.urlencode(secret_query)
        body = get(full, timeout, headers)
    sha = hashlib.sha256(body).hexdigest()
    rec = {"source_id": source_id, "url": url, "sha256": sha, "bytes": len(body), "fetched_at": now_utc()}
    if raw_dir is not None:
        dest = Path(raw_dir) / source_id
        dest.mkdir(parents=True, exist_ok=True)
        f = dest / (f"{sha[:12]}.{ext}" + (".gz" if gz else ""))
        if not f.exists():
            f.write_bytes(gzip.compress(body, 6) if gz else body)
        with (Path(raw_dir) / "index.jsonl").open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(rec) + "\n")
    return body, rec
