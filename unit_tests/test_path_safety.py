"""Security regression tests: path traversal must be rejected.

Covers the three traversal sinks flagged in the audit plus the shared
``web_api.storage`` helpers that fix them.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException
from fastapi.testclient import TestClient

from web_api import storage
from web_api.storage import is_safe_segment, resolve_within


class TestStorageHelpers(unittest.TestCase):
    def test_is_safe_segment_accepts_ids(self) -> None:
        for ok in ("abc123", "syn_pd_001", "run-1", "a.b_c-d"):
            self.assertTrue(is_safe_segment(ok), ok)

    def test_is_safe_segment_rejects_traversal(self) -> None:
        for bad in ("", ".", "..", "../x", "a/b", "/etc/passwd", "a\\b", "x\0y"):
            self.assertFalse(is_safe_segment(bad), bad)

    def test_resolve_within_allows_child(self) -> None:
        base = Path(tempfile.mkdtemp())
        try:
            got = resolve_within(base, "sub", "file.json")
            self.assertIsNotNone(got)
            self.assertTrue(str(got).startswith(str(base.resolve())))
        finally:
            shutil.rmtree(base, ignore_errors=True)

    def test_resolve_within_blocks_escape(self) -> None:
        base = Path(tempfile.mkdtemp())
        try:
            self.assertIsNone(resolve_within(base, "../../etc/hostname"))
            self.assertIsNone(resolve_within(base, "..", "..", "etc", "passwd"))
        finally:
            shutil.rmtree(base, ignore_errors=True)


class TestWebTraversalEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.mkdtemp(prefix="fg_pathsafe_")
        from web_api.main import app

        cls._real = storage.RUNS_DIR
        storage.RUNS_DIR = Path(cls._tmp)
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        storage.RUNS_DIR = cls._real
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def test_compare_rejects_traversal_run_ids(self) -> None:
        res = self.client.post(
            "/api/compare",
            json={"run_ids": ["../../etc", "../../passwd"]},
        )
        # Must not 500 / leak; rejected as bad request or not-found.
        self.assertIn(res.status_code, (400, 404), res.text)

    def test_run_detail_rejects_unsafe_run_id(self) -> None:
        # A single-segment but unsafe id reaches the handler; it must be
        # rejected by validation, never used to build a path.
        from web_api.run_history import load_run

        with self.assertRaises(HTTPException) as ctx:
            load_run("..")
        self.assertIn(ctx.exception.status_code, (400, 404))


class TestTemplateFilenameTraversal(unittest.TestCase):
    """`templateFilename` (attacker-controllable via an inline /api/runs config)
    must not escape the game_templates/ directory in IoManager.load_template."""

    def test_load_template_rejects_traversal(self) -> None:
        from src.io_managers.io_manager import IoManager

        io = IoManager()
        # Traversal via the filename half...
        with self.assertRaises(ValueError):
            io.load_template("../../../../etc/passwd", "en")
        # ...and via the language half (appended after the '_').
        with self.assertRaises(ValueError):
            io.load_template("pd", "../../../../etc/passwd")

    def test_load_template_allows_plain_name(self) -> None:
        # A normal flat name is contained; it just isn't found (no such file),
        # which is a FileNotFoundError, NOT the traversal ValueError.
        from src.io_managers.io_manager import IoManager

        io = IoManager()
        with self.assertRaises(FileNotFoundError):
            io.load_template("prisoner_dilemma", "en")


if __name__ == "__main__":
    unittest.main()
