"""Tests for the FastAPI app at ``fairgame_web``.

Uses Starlette's ``TestClient`` so the suite stays in-process and free
of any network or live LLM.

Coverage:

* /api/health returns the expected envelope.
* /api/presets walks resources/config and groups by category.
* /api/runs (POST with a preset) round-trips through the engine in
  demo mode and persists to results/web/<id>.
* /api/runs (GET list) reflects the new run.
* /api/runs/{id} returns the persisted rows.
* Legacy paths /health, /create_and_run_games, /translate_template
  308-redirect to their /api/* equivalents.
"""

from __future__ import annotations

import shutil
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TestFairgameWeb(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Isolate each test class from any prior runs so list_runs() is deterministic.
        runs_dir = PROJECT_ROOT / "results" / "web"
        if runs_dir.is_dir():
            shutil.rmtree(runs_dir)
        from fairgame_web import app  # late import: triggers logging config

        cls.client = TestClient(app)

    def tearDown(self) -> None:
        # Each /api/runs call toggles the LLM connector registry via
        # ``set_demo_mode``. Restore the conftest-registered fake
        # connectors so subsequent test files (test_experiment, …) still
        # see their expected registry.
        from src.demo_connector import restore_real_connectors

        restore_real_connectors()
        # conftest.py re-registers "Claude35Sonnet"/"OpenAIGPT4o"/etc. as
        # the deterministic fake at session start; restore_real_connectors
        # snapshots whatever was in MODEL_PROVIDER_MAP at *demo_connector
        # import time*, which already includes the conftest fakes if the
        # test session imported conftest first. So no extra re-registration
        # is needed here.

    def test_health_envelope(self) -> None:
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["status"], "OK")
        self.assertIn("demo_mode", body)

    def test_presets_listed_and_grouped(self) -> None:
        res = self.client.get("/api/presets")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertIn("presets", body)
        self.assertIn("by_category", body)
        # At least the canonical Prisoner's Dilemma is shipped.
        ids = [p["id"] for p in body["presets"]]
        self.assertTrue(
            any(i.startswith("prisoner_dilemma/") for i in ids),
            f"PD preset missing from {ids[:5]}…",
        )

    def test_run_flow_demo_mode_round_trips(self) -> None:
        res = self.client.post(
            "/api/runs",
            json={
                "preset": "prisoner_dilemma/prisoner_dilemma_round_known_conventional",
                "demo_mode": True,
            },
        )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertIn("id", body)
        self.assertIsInstance(body["rows"], list)
        self.assertGreater(len(body["rows"]), 0)
        # Per-run metadata must be persisted on disk.
        run_dir = PROJECT_ROOT / "results" / "web" / body["id"]
        self.assertTrue((run_dir / "metadata.json").is_file())
        self.assertTrue((run_dir / "results.csv").is_file())

        # The list endpoint reflects it.
        listed = self.client.get("/api/runs").json()["runs"]
        self.assertIn(body["id"], [r["id"] for r in listed])

        # Detail endpoint returns rows.
        detail = self.client.get(f"/api/runs/{body['id']}").json()
        self.assertEqual(detail["id"], body["id"])
        self.assertGreater(len(detail["rows"]), 0)

    def test_run_with_unknown_preset_errors_400(self) -> None:
        res = self.client.post(
            "/api/runs",
            json={"preset": "does/not/exist", "demo_mode": True},
        )
        self.assertEqual(res.status_code, 404, res.text)

    def test_run_without_config_or_preset_errors_400(self) -> None:
        res = self.client.post("/api/runs", json={"demo_mode": True})
        self.assertEqual(res.status_code, 400, res.text)

    def test_legacy_health_redirects(self) -> None:
        res = self.client.get("/health", follow_redirects=False)
        self.assertEqual(res.status_code, 308)
        self.assertEqual(res.headers["location"], "/api/health")

    def test_legacy_translate_redirects(self) -> None:
        res = self.client.post("/translate_template", json={}, follow_redirects=False)
        self.assertEqual(res.status_code, 308)
        self.assertEqual(res.headers["location"], "/api/translate")

    def test_legacy_create_and_run_redirects(self) -> None:
        res = self.client.post(
            "/create_and_run_games", json={}, follow_redirects=False
        )
        self.assertEqual(res.status_code, 308)
        self.assertEqual(res.headers["location"], "/api/runs")

    def test_root_serves_spa(self) -> None:
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("FAIRGAME", res.text)


if __name__ == "__main__":
    unittest.main()
