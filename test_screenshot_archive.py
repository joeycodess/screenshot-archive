import os
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from make_fixtures import generate
from screenshot_archive import run


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / "input"
        self.archive = self.root / "archive"
        generate(self.source, 3)

    def process(self, name, dry_run=False):
        return run(self.source, self.archive, self.root / (name + ".csv"), dry_run)

    def test_dry_run_apply_and_repeat(self):
        original = {file.name: (file.read_bytes(), file.stat().st_mtime_ns) for file in self.source.iterdir()}
        self.assertEqual([r[2] for r in self.process("plan", True)], ["would_archive"] * 3)
        self.assertFalse(self.archive.exists())
        self.assertEqual([r[2] for r in self.process("apply")], ["archived"] * 3)
        self.assertEqual([r[2] for r in self.process("repeat")], ["already_archived"] * 3)
        self.assertEqual(original, {file.name: (file.read_bytes(), file.stat().st_mtime_ns) for file in self.source.iterdir()})

    def test_duplicate_and_same_timestamp_different_content(self):
        first = self.source / "sample-0000.png"
        second = self.source / "sample-0001.png"
        duplicate = self.source / "duplicate.png"
        duplicate.write_bytes(first.read_bytes())
        for path in (second, duplicate):
            os.utime(path, ns=(first.stat().st_atime_ns, first.stat().st_mtime_ns))
        rows = self.process("plan", True)
        self.assertEqual(Counter(row[2] for row in rows), {"would_archive": 3, "duplicate_in_batch": 1})
        rows = self.process("apply")
        self.assertEqual(Counter(row[2] for row in rows), {"archived": 3, "already_archived": 1})
        self.assertEqual(len({row[1] for row in rows}), 3)

    def test_conflict_keeps_existing_bytes_and_invalid_input_is_reported(self):
        archived = self.process("apply")
        target = self.archive / archived[0][1]
        target.write_bytes(b"do not overwrite")
        (self.source / "invalid.jpg").write_bytes(b"text")
        self.assertEqual(Counter(row[2] for row in self.process("conflict")), {"error": 2, "already_archived": 2})
        self.assertEqual(target.read_bytes(), b"do not overwrite")

    def test_symlink_input_and_existing_manifest(self):
        (self.source / "alias.png").symlink_to(self.source / "sample-0000.png")
        self.assertEqual(self.process("plan", True)[0][2], "error")
        with self.assertRaises(FileExistsError):
            self.process("plan")

    def test_cli_exit_code_and_manifest(self):
        (self.source / "invalid.png").write_bytes(b"bad")
        manifest = self.root / "report.csv"
        result = subprocess.run(
            [sys.executable, "screenshot_archive.py", str(self.source), str(self.archive), "--manifest", str(manifest)],
            cwd=Path(__file__).parent, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("archived=3", result.stdout)
        self.assertIn("invalid.png,,error", manifest.read_text())

    def test_overlapping_paths_are_rejected(self):
        with self.assertRaises(ValueError):
            run(self.source, self.source / "archive", self.root / "report.csv")
