"""No personal name in the repository's own files, apart from copyright lines."""
import hashlib
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# LICENSE and NOTICE carry the copyright holder; doctrine/kit/ and tools/tic_archive.py are shared copies kept
# identical to their source repositories; history/ holds source records (WHO and OCHA text) that the update run
# commits, so a place or person named in a source never stops a run.
SKIP = ("doctrine/kit/", "tools/tic_archive.py", "LICENSE", "NOTICE", "history/")
WORD = re.compile(r"[^\W\d_]+")  # whole words: an accented letter stays inside its word
# Lower-case words, by SHA-256, so this file does not hold them.
WORDS = frozenset({
    "e1608f75c5d7813f3d4031cb30bfb786507d98137538ff8e128a6ff74e84e643",
    "1e79f6794931ef59a7825ea40e5b00346d48e7b6a9ada0904a3b9738b2baca92",
})


def hits(text):
    found = []
    for number, line in enumerate(text.splitlines(), 1):
        if line.startswith("Copyright "):
            continue
        spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", line)
        if any(hashlib.sha256(w.lower().encode()).hexdigest() in WORDS for w in WORD.findall(spaced)):
            found.append(number)
    return found


class NoNames(unittest.TestCase):
    def test_detects_a_listed_word_and_skips_copyright_lines(self):
        word = "".join(("T", "om"))
        self.assertEqual(hits("a\nset by " + word + "'s rule\nby" + word + " x\nCopyright 2026 " + word), [2, 3])
        self.assertEqual(hits("atom bottom custom"), [])

    def test_accented_words_are_not_split(self):
        place = "S" + chr(0xE3) + "o " + "".join(("T", "om")) + chr(0xE9) + " and Pr" + chr(0xED) + "ncipe"
        self.assertEqual(hits("Mpox - " + place), [])

    def test_history_records_are_not_scanned(self):
        self.assertTrue("history/who-notices.jsonl".startswith(SKIP))
        self.assertTrue("history/funding.jsonl".startswith(SKIP))

    def test_tracked_files_hold_no_personal_name(self):
        listed = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
        bad = []
        for name in listed.decode("utf-8").split("\0"):
            if not name or name.startswith(SKIP) or not (ROOT / name).is_file():
                continue
            data = (ROOT / name).read_bytes()
            if b"\0" in data:
                continue
            bad += [f"{name}:{n}" for n in hits(data.decode("utf-8", "replace"))]
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
