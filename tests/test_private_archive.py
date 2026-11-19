"""Private archive (19 Nov 2026, retention rule): update.yml sends the raw replies to the PRIVATE repo
metacog-osint/tic-archive after the deploy (tools/tic_archive.py). Live views are untouched: no program code changed."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest import mock
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.append(str(ROOT / "tools"))   # after ROOT: tools/<program>.py must not shadow the package
import tic_archive as ta  # noqa: E402

NOW = datetime(2026, 11, 19, 6, 0, tzinfo=timezone.utc)
PROGRAM = "relief"
WF = (ROOT / ".github" / "workflows" / "update.yml").read_text(encoding="utf-8")
STEP = WF[WF.index("- name: Private archive (raw replies, to tic-archive)"):]


def put(files: dict, **kw):
    with tempfile.TemporaryDirectory() as td:
        raw = Path(td) / "raw"
        for rel, text in files.items():
            (raw / rel).parent.mkdir(parents=True, exist_ok=True)
            (raw / rel).write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))
        store = ta.DirStore(Path(td) / "store")
        arch = ta.Archive(store, PROGRAM, "raw")
        doc = arch.put(raw, now=NOW, **kw)["doc"]
        arch.restore(Path(td) / "out")
        out = {p.relative_to(Path(td) / "out").as_posix(): p.read_bytes()
               for p in (Path(td) / "out").rglob("*") if p.is_file()}
        return doc, out


def step_args(flag):
    """Values given to one tic_archive.py flag in the workflow step."""
    toks = STEP.replace("\\n", " ").split()
    return [toks[i + 1].strip("'\"") for i, t in enumerate(toks) if t == flag]


class Workflow(unittest.TestCase):
    def test_step_after_deploy_with_private_token_and_loud_failure(self):
        self.assertLess(WF.index("- name: Deploy site/ to Cloudflare Pages"), WF.index(STEP[:40]))
        self.assertIn("GH_TOKEN: ${{ secrets.TIC_ARCHIVE_TOKEN }}", STEP)
        self.assertNotIn("github.token", STEP)
        self.assertIn(f"--program {PROGRAM} --lane raw --src data/raw", STEP)
        self.assertIn("exit 1", STEP)
        self.assertNotIn("|| true", STEP)

    def test_raw_never_published_by_this_repo(self):
        for chunk in WF.split("uses: actions/upload-artifact")[1:]:
            self.assertNotIn("data/raw", chunk.split("path:", 1)[1].split("\n", 1)[0])
        self.assertNotIn("data/raw", WF.split("cache/save", 1)[1].split("- name:", 1)[0] if "cache/save" in WF else "")


class Redaction(unittest.TestCase):
    @mock.patch.dict(os.environ)
    def test_appname_and_identifier_removed_rest_kept(self):
        self.assertEqual(step_args("--redact-env-if-set"), ["RELIEFWEB_APPNAME", "HDX_HAPI_APP_IDENTIFIER"])
        self.assertEqual(step_args("--redact-param"), ["appname", "app_identifier"])
        os.environ["RELIEFWEB_APPNAME"] = "tic-test-appname-1"
        os.environ.pop("HDX_HAPI_APP_IDENTIFIER", None)
        try:
            red = ta.Redactor([], step_args("--redact-param"), step_args("--redact-env-if-set"))
            import gzip
            doc, out = put({
                "reliefweb-disasters/aaa.json.gz": gzip.compress(
                    b'{"href":"https://api.reliefweb.int/v2/disasters?appname=tic-test-appname-1&limit=1000",'
                    b'"links":{"next":{"href":"https://api.reliefweb.int/v2/disasters?appname=tic-test-appname-1&offset=1000"}}}'),
                "who-don/bbb.json.gz": gzip.compress(b'{"value":[{"Title":"Cholera"}]}'),
                "index.jsonl": '{"url": "https://api.reliefweb.int/v2/disasters?limit=1000"}\n'}, redactor=red)
        finally:
            del os.environ["RELIEFWEB_APPNAME"]
        rw = gzip.decompress(out["reliefweb-disasters/aaa.json.gz"])
        self.assertNotIn(b"tic-test-appname-1", rw)
        self.assertIn(b"limit=1000", rw)
        self.assertEqual(gzip.decompress(out["who-don/bbb.json.gz"]), b'{"value":[{"Title":"Cholera"}]}')
        marks = {f["path"]: f.get("redacted", False) for f in doc["files"]}
        self.assertTrue(marks["reliefweb-disasters/aaa.json.gz"])
        self.assertFalse(marks["who-don/bbb.json.gz"])

    def test_workflow_passes_the_values_to_redact(self):
        self.assertIn("RELIEFWEB_APPNAME: ${{ secrets.RELIEFWEB_APPNAME }}", STEP)
        self.assertIn("HDX_HAPI_APP_IDENTIFIER: ${{ secrets.HDX_HAPI_APP_IDENTIFIER }}", STEP)


if __name__ == "__main__":
    unittest.main()
