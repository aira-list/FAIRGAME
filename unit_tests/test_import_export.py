"""Round-trip tests for configuration + results export/import bundles."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from unit_tests.support import RESOURCES_SKIP_REASON, resources_available

# setUpClass seeds templates read from the sibling resources folder (not shipped
# here); skip the whole module cleanly when it's absent.
pytestmark = pytest.mark.skipif(not resources_available(), reason=RESOURCES_SKIP_REASON)


def _leaf_config(name: str) -> dict:
    return {
        "name": name,
        "game_type_id": "gt_pd",
        "variation": "classic",
        "languages": ["en"],
        "game_config": {
            "nRounds": 1,
            "nRoundsIsKnown": True,
            "agentsCommunicate": False,
            "allAgentPermutations": False,
            "stopGameWhen": [],
            "agents": {
                "names": ["agent1", "agent2"],
                "personalities": {"en": ["cooperative", "selfish"]},
                "llmServices": ["OpenAIGPT4o", "OpenAIGPT4o"],
                "opponentPersonalityProb": [0, 0],
            },
            "payoffMatrix": {
                "weights": {"weight1": 3, "weight2": 5, "weight3": 0, "weight4": 1},
                "strategies": {"en": {"strategy1": "Cooperate", "strategy2": "Defect"}},
                "combinations": {
                    "combination1": ["strategy1", "strategy1"],
                    "combination2": ["strategy1", "strategy2"],
                    "combination3": ["strategy2", "strategy1"],
                    "combination4": ["strategy2", "strategy2"],
                },
                "matrix": {
                    "combination1": ["weight1", "weight1"],
                    "combination2": ["weight3", "weight2"],
                    "combination3": ["weight2", "weight3"],
                    "combination4": ["weight4", "weight4"],
                },
            },
            "llm": "OpenAIGPT4o",
            "seed": 42,
            "tomOrder": 0,
        },
    }


class TestConfigurationExportImport(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._runs = tempfile.mkdtemp(prefix="fg_ie_runs_")
        cls._data = tempfile.mkdtemp(prefix="fg_ie_data_")
        from web_api import storage
        from web_api.main import app

        cls._real_runs, cls._real_data = storage.RUNS_DIR, storage.DATA_DIR
        storage.RUNS_DIR = Path(cls._runs)
        storage.DATA_DIR = Path(cls._data)
        gt = storage.RESOURCES_DIR / "game_templates"
        storage.save_store(
            "game_types",
            [
                {
                    "id": "gt_pd",
                    "name": "Prisoner's Dilemma",
                    "description": "x",
                    "created_at": "2026-04-29T20:00:00",
                }
            ],
        )
        storage.save_store(
            "templates",
            [
                {
                    "id": "tpl_pd",
                    "game_type_id": "gt_pd",
                    "variation": "classic",
                    "language": "en",
                    "body": (gt / "prisoner_dilemma_en.txt").read_text(),
                    "source_template_id": None,
                    "source_language": None,
                    "created_at": "2026-04-29T20:00:00",
                }
            ],
        )
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        from web_api import storage

        storage.RUNS_DIR, storage.DATA_DIR = cls._real_runs, cls._real_data
        for d in (cls._runs, cls._data):
            shutil.rmtree(d, ignore_errors=True)

    def _make_config_with_run(self, name: str) -> tuple[str, str]:
        cid = self.client.post("/api/configurations", json=_leaf_config(name)).json()["id"]
        res = self.client.post(f"/api/configurations/{cid}/run", params={"demo_mode": "true"})
        self.assertEqual(res.status_code, 200, res.text)
        return cid, res.json()["id"]

    def test_run_records_configuration_id(self) -> None:
        cid, run_id = self._make_config_with_run("PD-link")
        run = self.client.get(f"/api/runs/{run_id}").json()
        self.assertEqual(run["configuration_id"], cid)

    def test_export_bundle_shape(self) -> None:
        cid, _ = self._make_config_with_run("PD-export")
        bundle = self.client.get(f"/api/configurations/{cid}/export").json()
        self.assertEqual(bundle["fairgame_bundle"], "1")
        self.assertEqual(bundle["configuration"]["id"], cid)
        self.assertEqual(bundle["game_type"]["id"], "gt_pd")
        self.assertGreaterEqual(len(bundle["templates"]), 1)
        self.assertEqual(len(bundle["runs"]), 1)
        self.assertIn("rows", bundle["runs"][0])
        self.assertGreater(len(bundle["runs"][0]["rows"]), 0)

    def test_export_missing_config_404(self) -> None:
        self.assertEqual(self.client.get("/api/configurations/nope/export").status_code, 404)

    def test_round_trip_recreates_config_and_runs(self) -> None:
        cid, run_id = self._make_config_with_run("PD-roundtrip")
        bundle = self.client.get(f"/api/configurations/{cid}/export").json()
        original_rows = bundle["runs"][0]["rows"]

        res = self.client.post("/api/import", json=bundle)
        self.assertEqual(res.status_code, 200, res.text)
        out = res.json()

        new_cid = out["configuration"]["id"]
        self.assertNotEqual(new_cid, cid, "import must mint a fresh configuration id")
        self.assertEqual(out["imported_runs"], 1)
        # Collision-safe rename since the source name still exists.
        self.assertEqual(out["configuration"]["name"], "PD-roundtrip (imported)")

        # The imported run is linked to the NEW configuration and round-trips rows.
        imported_runs = [
            r
            for r in self.client.get("/api/runs").json()["runs"]
            if r["configuration_id"] == new_cid
        ]
        self.assertEqual(len(imported_runs), 1)
        detail = self.client.get(f"/api/runs/{imported_runs[0]['id']}").json()
        self.assertEqual(len(detail["rows"]), len(original_rows))

    def test_import_rejects_unknown_version(self) -> None:
        res = self.client.post(
            "/api/import",
            json={
                "fairgame_bundle": "999",
                "configuration": _leaf_config("x"),
            },
        )
        self.assertEqual(res.status_code, 400)

    def test_import_does_not_duplicate_existing_tag(self) -> None:
        cid, _ = self._make_config_with_run("PD-tagdup")
        bundle = self.client.get(f"/api/configurations/{cid}/export").json()
        before = len(self.client.get("/api/game-types").json()["game_types"])
        self.client.post("/api/import", json=bundle)
        after = len(self.client.get("/api/game-types").json()["game_types"])
        self.assertEqual(before, after, "re-importing should reuse the existing game type")


if __name__ == "__main__":
    unittest.main()
