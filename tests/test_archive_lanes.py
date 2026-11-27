"""Private archive lanes: every file a run of update.yml leaves outside the tracked code (data/, history/, site/)
lands in the private archive (tools/tic_archive.py, metacog-osint/tic-archive) and restores byte for byte. A file
that a later run removes or replaces stays restorable from the snapshot that held it.

The test makes a real offline run in a temporary folder (collect from the fixtures, build, the retention archive,
the full appeal records, the kit's history log as the workflow calls it), then runs the workflow's own
tic_archive.py commands, read from update.yml, against a local DirStore. Nothing reaches GitHub: GhStore is replaced
by the DirStore and any subprocess call during an archive command fails the test."""
from __future__ import annotations

import gzip
import hashlib
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "doctrine" / "kit" / "python"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.append(str(ROOT / "tools"))   # after ROOT: tools/<program>.py must not shadow the package
import tic_archive as ta  # noqa: E402
from relief import archive  # noqa: E402
from test_relief import KEYS, NOW, cli, getter  # noqa: E402

WF = (ROOT / ".github" / "workflows" / "update.yml").read_text(encoding="utf-8")
PROGRAM = "relief"
RUN_OUTPUTS = ("data", "history", "site")          # what a run writes beside the tracked code
RUN_INPUTS = ("doctrine", "site_src")              # tracked code the offline run is given
LANES = {"raw", "appeals", "history", "state", "site"}
FIRST, SECOND = "20261116T020000Z", "20261116T080000Z"


def steps() -> dict[str, str]:
    """The workflow's steps by name (unnamed `uses:` steps by their action)."""
    out = {}
    for chunk in re.split(r"(?m)^      - ", WF.split("\n    steps:\n", 1)[1])[1:]:
        m = re.match(r"name: (.+)|uses: (\S+)", chunk)
        out[(m.group(1) or m.group(2)).strip()] = chunk
    return out


STEPS = steps()


def step(prefix: str) -> str:
    (name,) = [n for n in STEPS if n.startswith(prefix)]
    return STEPS[name]


def archive_calls(text: str, cmd: str) -> list[list[str]]:
    """Every `python tools/tic_archive.py <cmd> ...` in a step, as argv after the script name."""
    flat = text.replace("\\\n", " ")
    return [[m.group(1), *shlex.split(m.group(2))]
            for m in re.finditer(r"python tools/tic_archive\.py (" + cmd + r")\b([^;|&\n]*)", flat)]


def arg(argv: list[str], flag: str) -> list[str]:
    return [argv[i + 1] for i, t in enumerate(argv) if t == flag]


def put_calls() -> list[list[str]]:
    """Every put the workflow makes: lane appeals in the History step, the rest in the Private archive steps."""
    return [c for name in STEPS if name.startswith(("Private archive", "History"))
            for c in archive_calls(STEPS[name], "put")]


def tree(root: Path) -> dict[str, str]:
    """{posix path relative to root: sha256} for every file."""
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


def run_archive(argv: list[str], cwd: Path, store: Path, stamp: str = FIRST, keys: dict | None = None) -> int:
    """One tic_archive.py command as the workflow gives it, in cwd, against a DirStore at store. The keys are unset
    unless given (as when the secrets are set)."""
    def no_subprocess(*a, **k):
        raise AssertionError("an archive command tried to run a subprocess (gh): nothing may leave the test")

    old = os.getcwd()
    os.chdir(cwd)
    try:
        env = {k: v for k, v in os.environ.items() if k not in (*KEYS, "GH_TOKEN")}
        env.update(keys or {})
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(ta, "GhStore", lambda *a, **k: ta.DirStore(store)), \
                mock.patch.object(ta, "utc_stamp", lambda now=None: stamp), \
                mock.patch.object(subprocess, "run", no_subprocess):
            return ta.main(argv)
    finally:
        os.chdir(old)


class RunTree:
    """A real offline run, made once: collect, build, the retention archive, the private appeals file and the
    kit's history log, each as update.yml calls it."""
    tmp: Path | None = None

    @classmethod
    def make(cls) -> Path:
        if cls.tmp is not None:
            return cls.tmp
        tmp = Path(tempfile.mkdtemp(prefix="relief-lanes-"))
        for d in RUN_INPUTS:
            shutil.copytree(ROOT / d, tmp / d)
        snap = cli.collect(tmp, getter=getter, now=NOW, keys=KEYS)
        cli.build_site(tmp)
        # A closed day of the history log, as an older run leaves it.
        day = tmp / "history" / "log" / "2026" / "11" / "15.jsonl.gz"
        day.parent.mkdir(parents=True, exist_ok=True)
        day.write_bytes(gzip.compress(b'{"format":"tic-history/1","change":"new","id":"relief:old"}\n', 9, mtime=0))
        archive.run(snap, tmp / "history")                                      # relief.py archive
        archive.run_full(snap, tmp / "data" / "private" / "appeals")            # relief.py archive-full
        (kit,) = re.findall(r"python (doctrine/kit/tic\.py history [^|;\n]*)", step("History").replace("\\\n", " "))
        r = subprocess.run([sys.executable, *shlex.split(kit)], cwd=tmp, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"kit history failed: {r.stderr[-400:]}")
        cls.tmp = tmp
        return tmp


def tearDownModule():
    if RunTree.tmp is not None:
        shutil.rmtree(RunTree.tmp, ignore_errors=True)


class TestWorkflowLanes(unittest.TestCase):
    def test_lanes_and_their_folders(self):
        lanes = {arg(c, "--lane")[0]: c for c in put_calls()}
        self.assertEqual(set(lanes), LANES)
        for c in lanes.values():
            self.assertEqual(arg(c, "--program"), [PROGRAM])
        self.assertEqual(arg(lanes["raw"], "--src"), ["data/raw"])
        self.assertEqual(arg(lanes["appeals"], "--src"), ["data/private/appeals"])
        self.assertEqual(arg(lanes["history"], "--src"), ["history"])
        self.assertEqual(arg(lanes["state"], "--src"), ["data"])
        self.assertEqual(arg(lanes["state"], "--exclude"), ["raw/*", "private/*"])   # each has its own lane
        self.assertEqual(arg(lanes["site"], "--src"), ["site"])
        # history/ and site/ are public: archived as they are, so they match the public copy by hash.
        for lane in ("history", "site"):
            self.assertFalse([t for t in lanes[lane] if t.startswith("--redact")], lane)
        # The snapshot never holds the keys (collect strips them); their values are replaced as in lane raw, in
        # case. No --redact-param there: it rewrites any "appname=..." text, so the snapshot would not restore
        # byte for byte (TestSnapshotRestoreFromTheArchive).
        self.assertEqual(arg(lanes["state"], "--redact-env-if-set"), arg(lanes["raw"], "--redact-env-if-set"))
        self.assertEqual(arg(lanes["state"], "--redact-param"), [])

    def test_step_after_the_deploy_and_loud_on_failure(self):
        names = list(STEPS)
        new = names.index("Private archive (history, run snapshot and site, to tic-archive)")
        self.assertGreater(new, names.index("Deploy site/ to Cloudflare Pages"))
        self.assertGreater(new, names.index("Private archive (raw replies, to tic-archive)"))
        text = STEPS[names[new]]
        self.assertIn("if: ${{ !cancelled() }}", text)
        self.assertIn("GH_TOKEN: ${{ secrets.TIC_ARCHIVE_TOKEN }}", text)
        self.assertIn("RELIEFWEB_APPNAME: ${{ secrets.RELIEFWEB_APPNAME }}", text)
        self.assertIn("HDX_HAPI_APP_IDENTIFIER: ${{ secrets.HDX_HAPI_APP_IDENTIFIER }}", text)
        self.assertNotIn("github.token", text)
        self.assertNotIn("|| true", text)
        self.assertIn('[ -z "$GH_TOKEN" ]', text)
        self.assertEqual(text.count("exit 1"), 2)            # token missing; any lane failed
        self.assertEqual(text.count("|| failed=1"), 3)       # each lane tried even if another failed

    def test_each_lane_only_after_the_step_that_writes_it(self):
        text = step("Private archive (history")
        self.assertIn("HISTORY: ${{ steps.history.outcome }}", text)
        self.assertIn("CHECKED: ${{ steps.check.outcome }}", text)
        # The deploy step also succeeds when it skips itself, so the site lane waits for its output, not its outcome.
        self.assertIn("DEPLOYED: ${{ steps.deploy.outputs.deployed }}", text)
        self.assertIn("id: history", step("History"))
        self.assertIn("id: check", step("Check (registers"))
        self.assertIn("id: deploy", step("Deploy site/"))
        flat = text.replace("\\\n", " ")
        for var, value, lane in (("HISTORY", "success", "history"), ("CHECKED", "success", "state"),
                                 ("DEPLOYED", "true", "site")):
            self.assertRegex(flat, r'if \[ "\$' + var + r'" = "' + value + r'" \]; then\s+python tools/tic_archive\.py '
                                   r'put --program relief --lane ' + lane + ' ')

    def test_what_the_workflow_keeps_for_a_while_or_replaces_is_inside_the_archived_folders(self):
        # The Actions cache (evicted after 7 days) holds this path; the state lane takes data/ without raw/private.
        for name in ("Keep this run's snapshot for the next run",
                     "Last run's snapshot from the Actions cache (none on the first run)"):
            self.assertEqual(re.findall(r"(?m)^\s+path: (\S+)\s*$", STEPS[name]), ["data/snapshot.json"])
        self.assertIn("git add history\n", step("History"))
        self.assertIn("pages deploy site --project-name", step("Deploy site/"))


class TestEveryRunFileIsArchived(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.run_root = RunTree.make()
        cls.work = Path(tempfile.mkdtemp(prefix="relief-store-"))
        cls.store = cls.work / "store"
        cls.before = {top: tree(cls.run_root / top) for top in RUN_OUTPUTS}
        cls.results = {arg(argv, "--lane")[0]: run_archive(argv, cls.run_root, cls.store, FIRST)
                       for argv in put_calls()}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.work, ignore_errors=True)

    def restore_all(self, dest: Path, snapshots: dict[str, str] | None = None) -> dict[str, str]:
        """Every lane restored, mapped back to run-tree paths: {path: sha256}."""
        got = {}
        for argv in put_calls():
            lane, (src,) = arg(argv, "--lane")[0], arg(argv, "--src")
            cmd = ["restore", "--program", PROGRAM, "--lane", lane, "--dest", str(dest / lane)]
            if snapshots and lane in snapshots:
                cmd += ["--snapshot", snapshots[lane]]
            self.assertEqual(run_archive(cmd, self.run_root, self.store), 0, lane)
            for rel, sha in tree(dest / lane).items():
                path = f"{src}/{rel}"
                self.assertNotIn(path, got, "two lanes hold the same file")
                got[path] = sha
        return got

    def snapshot_names(self, stamp: str) -> dict[str, str]:
        out = {}
        for tag in self.store.iterdir():
            for p in tag.iterdir():
                if p.name.startswith(stamp) and p.name.endswith(".files.json"):
                    out[tag.name[len(PROGRAM) + 1:].rsplit("-", 2)[0]] = p.name
        return out

    def test_the_offline_run_writes_only_the_known_folders(self):
        self.assertEqual({p.name for p in self.run_root.iterdir()}, set(RUN_INPUTS) | set(RUN_OUTPUTS))
        self.assertTrue(self.before["data"] and self.before["history"] and self.before["site"])

    def test_every_put_succeeded(self):
        self.assertEqual(self.results, {lane: 0 for lane in LANES})

    def test_every_file_of_the_run_restores_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as td:
            got = self.restore_all(Path(td), self.snapshot_names(FIRST))
        want = {f"{top}/{rel}": sha for top, files in self.before.items() for rel, sha in files.items()}
        self.assertEqual(sorted(set(want) - set(got)), [], "files of the run missing from the archive")
        self.assertEqual(sorted(set(got) - set(want)), [], "the archive holds files the run did not write")
        self.assertEqual({p: s for p, s in got.items() if want[p] != s}, {}, "restored bytes differ")
        for p in ("site/data/feed.geojson", "site/data/ended.geojson", "site/data/snapshot.json",
                  "data/snapshot.json", "data/raw/index.jsonl", "data/private/appeals/appeals.jsonl",
                  "history/state.json", "history/appeals-index.jsonl", "history/appeals-counts.json",
                  "history/who-notices.jsonl", "history/funding.jsonl", "history/reliefweb-counts.jsonl",
                  "history/log/2026/11/15.jsonl.gz", "history/log/2026/11/16.jsonl"):
            self.assertIn(p, got)

    def test_removed_or_replaced_files_stay_restorable(self):
        root = self.run_root
        old = {p: (root / p).read_bytes() for p in ("history/log/2026/11/15.jsonl.gz", "history/appeals-counts.json",
                                                     "data/snapshot.json", "site/data/feed.geojson")}
        try:
            # The next run: a closed log day no longer in the public tree (a cap), rewritten counts, a new
            # snapshot, a new deploy.
            (root / "history/log/2026/11/15.jsonl.gz").unlink()
            for p in ("history/appeals-counts.json", "site/data/feed.geojson"):
                (root / p).write_bytes(old[p] + b"\n")
            (root / "data/snapshot.json").write_bytes(old["data/snapshot.json"].replace(b"{", b'{"run": 2, ', 1))
            for argv in put_calls():
                if arg(argv, "--lane")[0] in ("history", "state", "site"):
                    self.assertEqual(run_archive(argv, root, self.store, SECOND), 0)
            first, second = self.snapshot_names(FIRST), self.snapshot_names(SECOND)
            self.assertEqual(set(first), LANES)
            self.assertEqual(set(second), {"history", "state", "site"})
            with tempfile.TemporaryDirectory() as td:
                now = self.restore_all(Path(td) / "now")
                then = self.restore_all(Path(td) / "then", first)
            self.assertNotIn("history/log/2026/11/15.jsonl.gz", now)
            for p, data in old.items():
                self.assertEqual(then[p], hashlib.sha256(data).hexdigest(), p)
                if (root / p).exists():
                    self.assertEqual(now[p], hashlib.sha256((root / p).read_bytes()).hexdigest(), p)
                    self.assertNotEqual(now[p], then[p], p)
        finally:
            for p, data in old.items():
                (root / p).parent.mkdir(parents=True, exist_ok=True)
                (root / p).write_bytes(data)


class TestSnapshotRestoreFromTheArchive(unittest.TestCase):
    """The run snapshot is read back from the private archive when the Actions cache has none."""

    def test_only_on_a_cache_miss_and_through_a_temporary_folder(self):
        text = step("No cache entry, so the snapshot from the private archive")
        self.assertIn("if: steps.state.outputs.cache-matched-key == ''", text)
        self.assertIn("GH_TOKEN: ${{ secrets.TIC_ARCHIVE_TOKEN }}", text)
        self.assertNotIn("exit 1", text)                       # a miss never stops the run
        (call,) = archive_calls(text, "restore")
        self.assertEqual(arg(call, "--program"), [PROGRAM])
        self.assertEqual(arg(call, "--lane"), ["state"])
        self.assertEqual(arg(call, "--dest"), ["$RUNNER_TEMP/archive-state"])        # not data/ itself
        self.assertLess(text.index("tic_archive.py restore"),
                        text.index('cp "$RUNNER_TEMP/archive-state/snapshot.json" data/snapshot.json'))
        names = list(STEPS)
        self.assertLess(names.index("No cache entry, so the snapshot from the private archive (or none)"),
                        names.index("Live collection (a failed lane keeps its last good copy and says so on the page)"))

    def test_restore_gives_back_the_snapshot_the_cache_holds(self):
        run_root = RunTree.make()
        (call,) = archive_calls(step("No cache entry, so the snapshot from the private archive"), "restore")
        (state_put,) = [c for c in put_calls() if arg(c, "--lane") == ["state"]]
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            self.assertEqual(run_archive(state_put, run_root, td / "store"), 0)
            fresh, runner_temp = td / "next-run", td / "runner-temp"
            fresh.mkdir()
            argv = [t.replace("$RUNNER_TEMP", str(runner_temp)) for t in call]
            self.assertEqual(run_archive(argv, fresh, td / "store"), 0)
            self.assertEqual(sorted(tree(runner_temp / "archive-state")), ["snapshot.json"])
            self.assertEqual((runner_temp / "archive-state" / "snapshot.json").read_bytes(),
                             (run_root / "data" / "snapshot.json").read_bytes())

    def state_round_trip(self, snapshot: bytes, keys: dict | None = None) -> bytes:
        """data/snapshot.json through the workflow's state put and its cache-miss restore; the bytes restored."""
        (call,) = archive_calls(step("No cache entry, so the snapshot from the private archive"), "restore")
        (state_put,) = [c for c in put_calls() if arg(c, "--lane") == ["state"]]
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            run = td / "run"
            (run / "data").mkdir(parents=True)
            (run / "data" / "snapshot.json").write_bytes(snapshot)
            self.assertEqual(run_archive(state_put, run, td / "store", keys=keys), 0)
            fresh, runner_temp = td / "next-run", td / "runner-temp"
            fresh.mkdir()
            argv = [t.replace("$RUNNER_TEMP", str(runner_temp)) for t in call]
            self.assertEqual(run_archive(argv, fresh, td / "store"), 0)
            return (runner_temp / "archive-state" / "snapshot.json").read_bytes()

    def test_text_that_looks_like_a_key_parameter_restores_byte_for_byte(self):
        # Not a key: text a record could hold. Only key values are replaced in this lane, so the next run gets the
        # snapshot exactly as the run before wrote it.
        snap = (b'{"records": {"ifrc": [{"note": "https://example.org/a?appname=abc123&x=1 app_identifier=zz9"}]},\n'
                b' "lanes": {"reliefweb": {"error": "URLError: appname=<key>"}}}\n')
        self.assertEqual(self.state_round_trip(snap), snap)

    def test_a_key_value_in_the_snapshot_is_still_replaced(self):
        value = KEYS["RELIEFWEB_APPNAME"]
        snap = ('{"lanes": {"reliefweb": {"error": "leaked ' + value + '"}}}\n').encode()
        got = self.state_round_trip(snap, keys=KEYS)
        self.assertNotIn(value.encode(), got)
        self.assertEqual(got, snap.replace(value.encode(), b"REDACTED"))


BASH = shutil.which("bash")


def run_script(text: str) -> str:
    """The `run: |` block of a step, as the runner gets it."""
    lines = text.split("run: |\n", 1)[1].split("\n")
    body = []
    for line in lines:
        if line.strip() and not line.startswith(" " * 10):
            break
        body.append(line[10:])
    return "\n".join(body) + "\n"


def step_env(text: str, given: dict) -> dict:
    """The step's env block, its ${{ }} expressions evaluated from given: {"steps.deploy.outcome": ...,
    "steps.deploy.outputs.deployed": ..., "secrets.X": ..., "vars.X": ...}; a term not given is empty."""
    env = {}
    for name, expr in re.findall(r"(?m)^ {10}([A-Z_]+): \$\{\{ (.+?) \}\}", text.split("run: |\n", 1)[0]):
        env[name] = next((given[t] for t in (t.strip() for t in expr.split("||")) if given.get(t)), "")
    return env


@unittest.skipUnless(BASH, "needs bash, as the runner has")
class TestSiteLaneOnlyAfterARealDeploy(unittest.TestCase):
    """The deploy step and the archive step's lane choice run in bash as the runner runs them, with wrangler and the
    archive tool replaced by stubs. The deploy step ends `success` when it skips itself (no Cloudflare secrets), so
    the site lane must not take that as a deploy."""

    def bash(self, script: str, env: dict, td: Path, stubs: str) -> int:
        full = {k: v for k, v in os.environ.items() if k in ("PATH", "SYSTEMROOT", "TEMP", "TMP", "HOME")}
        full.update(env, CALLS=(td / "calls").as_posix(), GITHUB_OUTPUT=(td / "output").as_posix())
        r = subprocess.run([BASH, "--noprofile", "--norc", "-eo", "pipefail", "-c", stubs + script], env=full,
                           capture_output=True, text=True, timeout=60)
        return r.returncode

    def run_case(self, secrets: dict, npx_rc: int) -> tuple[int, list[str], list[str]]:
        """(deploy step exit code, wrangler calls, lanes the archive step put)."""
        deploy, archive_step = step("Deploy site/"), step("Private archive (history")
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            stubs = ('npx() { echo "npx $*" >> "$CALLS"; return ' + str(npx_rc) + '; }\nsleep() { :; }\n')
            rc = self.bash(run_script(deploy), step_env(deploy, secrets), td, stubs)
            calls = (td / "calls").read_text().splitlines() if (td / "calls").exists() else []
            out = dict(line.split("=", 1) for line in (td / "output").read_text().splitlines()) \
                if (td / "output").exists() else {}
            given = {"secrets.TIC_ARCHIVE_TOKEN": "token", "steps.history.outcome": "success",
                     "steps.check.outcome": "success", "steps.deploy.outcome": "success" if rc == 0 else "failure"}
            given.update({f"steps.deploy.outputs.{k}": v for k, v in out.items()})
            (td / "calls").unlink(missing_ok=True)
            self.assertEqual(self.bash(run_script(archive_step), step_env(archive_step, given), td,
                                       'python() { echo "$*" >> "$CALLS"; }\n'), 0)
            puts = (td / "calls").read_text().splitlines()
            lanes = [arg(shlex.split(p), "--lane")[0] for p in puts if p.startswith("tools/tic_archive.py put")]
            return rc, calls, lanes

    def test_skipped_deploy_is_not_archived_as_deployed(self):
        rc, calls, lanes = self.run_case({}, 0)
        self.assertEqual((rc, calls), (0, []))          # the step skipped itself and still succeeded
        self.assertEqual(lanes, ["history", "state"])

    def test_real_deploy_is_archived(self):
        rc, calls, lanes = self.run_case({"secrets.CLOUDFLARE_PAGES_TOKEN": "t", "vars.CLOUDFLARE_ACCOUNT_ID": "a"}, 0)
        self.assertEqual((rc, len(calls)), (0, 1))
        self.assertEqual(lanes, ["history", "state", "site"])

    def test_failed_deploy_is_not_archived(self):
        rc, calls, lanes = self.run_case({"secrets.CLOUDFLARE_PAGES_TOKEN": "t", "vars.CLOUDFLARE_ACCOUNT_ID": "a"}, 1)
        self.assertEqual((rc, len(calls)), (1, 3))      # three tries, then the step fails
        self.assertEqual(lanes, ["history", "state"])


if __name__ == "__main__":
    unittest.main()
