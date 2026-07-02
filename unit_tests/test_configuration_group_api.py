"""HTTP-level tests for configuration groups (variations + collisions + clone + run-variant)."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


def _make_pd_matrix(w1: int = 3) -> dict:
    return {
        "weights": {"weight1": w1, "weight2": 5, "weight3": 0, "weight4": 1},
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
    }


def _group_body(name: str, variants: list) -> dict:
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
            "llm": "OpenAIGPT4o",
            "seed": 42,
        },
        "variations": variants,
    }


def _leaf_body(name: str, w1: int = 3) -> dict:
    body = _group_body(name, [])
    body["game_config"]["payoffMatrix"] = _make_pd_matrix(w1)
    body.pop("variations")
    return body


class TestConfigurationGroupsAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.mkdtemp(prefix="fg_cfg_groups_")
        cls._tmp_data = tempfile.mkdtemp(prefix="fg_data_")
        from web_api import storage
        from web_api.main import app

        cls._real_runs = storage.RUNS_DIR
        cls._real_data = storage.DATA_DIR
        storage.RUNS_DIR = Path(cls._tmp)
        storage.DATA_DIR = Path(cls._tmp_data)
        # The library ships empty, so seed the PD template these run tests
        # resolve against (gt_pd / classic / en).
        gt = storage.RESOURCES_DIR / "game_templates"
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

        storage.RUNS_DIR = cls._real_runs
        storage.DATA_DIR = cls._real_data
        shutil.rmtree(cls._tmp, ignore_errors=True)
        shutil.rmtree(cls._tmp_data, ignore_errors=True)

    def tearDown(self) -> None:
        # Wipe the configurations store between tests so each test gets a
        # blank slate (the seed defaults are re-loaded on next access).
        from web_api.storage import save_store

        save_store("configurations", [])

    # ---- save / load / list ----

    def test_create_group_saves_with_variations(self) -> None:
        body = _group_body(
            "PD-sweep",
            [
                {"axis": "payoffMatrix", "name": "mild", "value": _make_pd_matrix(2)},
                {"axis": "payoffMatrix", "name": "harsh", "value": _make_pd_matrix(5)},
            ],
        )
        res = self.client.post("/api/configurations", json=body)
        self.assertEqual(res.status_code, 200, res.text)
        saved = res.json()
        self.assertIn("id", saved)
        self.assertEqual(saved["name"], "PD-sweep")
        self.assertEqual(len(saved["variations"]), 2)
        self.assertEqual(saved["variations"][0]["name"], "mild")

    def test_listing_includes_variations_for_groups(self) -> None:
        self.client.post(
            "/api/configurations",
            json=_group_body(
                "PD-sweep",
                [
                    {"axis": "payoffMatrix", "name": "mild", "value": _make_pd_matrix(2)},
                ],
            ),
        )
        listed = self.client.get("/api/configurations").json()["configurations"]
        match = next(c for c in listed if c["name"] == "PD-sweep")
        self.assertEqual([v["name"] for v in match["variations"]], ["mild"])

    # ---- collisions ----

    def test_create_group_rejects_when_resolved_name_already_exists(self) -> None:
        # Pre-existing leaf occupies the resolved name "PD · mild".
        leaf = self.client.post("/api/configurations", json=_leaf_body("PD · mild"))
        self.assertEqual(leaf.status_code, 200)
        # Now try to save a group whose first variant resolves to the same name.
        res = self.client.post(
            "/api/configurations",
            json=_group_body(
                "PD",
                [
                    {"axis": "payoffMatrix", "name": "mild", "value": _make_pd_matrix(2)},
                ],
            ),
        )
        self.assertEqual(res.status_code, 409, res.text)
        self.assertIn("PD · mild", res.json()["detail"])

    def test_create_leaf_rejects_when_colliding_with_group_variant(self) -> None:
        self.client.post(
            "/api/configurations",
            json=_group_body(
                "Sweep",
                [
                    {"axis": "payoffMatrix", "name": "one", "value": _make_pd_matrix(2)},
                ],
            ),
        )
        res = self.client.post("/api/configurations", json=_leaf_body("Sweep · one"))
        self.assertEqual(res.status_code, 409, res.text)
        self.assertIn("Sweep · one", res.json()["detail"])

    def test_group_with_internal_duplicate_variant_names_rejected(self) -> None:
        res = self.client.post(
            "/api/configurations",
            json=_group_body(
                "Sweep",
                [
                    {"axis": "payoffMatrix", "name": "x", "value": _make_pd_matrix(2)},
                    {"axis": "payoffMatrix", "name": "x", "value": _make_pd_matrix(5)},
                ],
            ),
        )
        self.assertEqual(res.status_code, 409, res.text)

    def test_update_does_not_collide_with_self(self) -> None:
        created = self.client.post("/api/configurations", json=_leaf_body("PD-toy")).json()
        # PUT with same name on same id must succeed.
        res = self.client.put(
            f"/api/configurations/{created['id']}",
            json=_leaf_body("PD-toy"),
        )
        self.assertEqual(res.status_code, 200, res.text)

    # ---- clone ----

    def test_clone_leaf_creates_a_new_leaf_with_copy_suffix(self) -> None:
        original = self.client.post(
            "/api/configurations",
            json=_leaf_body("PD-toy", w1=7),
        ).json()
        res = self.client.post(f"/api/configurations/{original['id']}/clone")
        self.assertEqual(res.status_code, 200, res.text)
        clone = res.json()
        self.assertNotEqual(clone["id"], original["id"])
        self.assertTrue(clone["name"].startswith("PD-toy"))
        self.assertNotEqual(clone["name"], original["name"])  # name suffixed
        # Underlying matrix is preserved (w1 = 7).
        self.assertEqual(
            clone["game_config"]["payoffMatrix"]["weights"]["weight1"],
            7,
        )

    def test_clone_group_clones_all_variants(self) -> None:
        original = self.client.post(
            "/api/configurations",
            json=_group_body(
                "Sweep",
                [
                    {"axis": "payoffMatrix", "name": "mild", "value": _make_pd_matrix(2)},
                    {"axis": "payoffMatrix", "name": "harsh", "value": _make_pd_matrix(5)},
                ],
            ),
        ).json()
        res = self.client.post(f"/api/configurations/{original['id']}/clone")
        self.assertEqual(res.status_code, 200, res.text)
        clone = res.json()
        self.assertEqual(
            sorted(v["name"] for v in clone["variations"]),
            ["harsh", "mild"],
        )
        # Per-variant value is deep-copied (not aliasing the original).
        self.assertEqual(
            clone["variations"][0]["value"]["weights"]["weight1"],
            2,
        )

    def test_clone_when_default_name_collides_appends_a_number(self) -> None:
        # Two clones in a row must each get a unique name.
        original = self.client.post(
            "/api/configurations",
            json=_leaf_body("PD-toy"),
        ).json()
        first = self.client.post(f"/api/configurations/{original['id']}/clone").json()
        second = self.client.post(f"/api/configurations/{original['id']}/clone").json()
        self.assertNotEqual(first["name"], second["name"])

    # ---- run a single variant of a group ----

    def test_run_a_specific_variant_produces_rows(self) -> None:
        created = self.client.post(
            "/api/configurations",
            json=_group_body(
                "PD-sweep",
                [
                    {"axis": "payoffMatrix", "name": "mild", "value": _make_pd_matrix(2)},
                    {"axis": "payoffMatrix", "name": "harsh", "value": _make_pd_matrix(5)},
                ],
            ),
        ).json()
        res = self.client.post(
            f"/api/configurations/{created['id']}/run",
            params={"demo_mode": "true", "variant": "harsh"},
        )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertGreater(len(body["rows"]), 0)
        self.assertEqual(body["variant"], "harsh")

    def test_run_group_without_variant_param_errors(self) -> None:
        created = self.client.post(
            "/api/configurations",
            json=_group_body(
                "Sweep",
                [
                    {"axis": "payoffMatrix", "name": "one", "value": _make_pd_matrix(2)},
                ],
            ),
        ).json()
        res = self.client.post(
            f"/api/configurations/{created['id']}/run",
            params={"demo_mode": "true"},
        )
        self.assertEqual(res.status_code, 400, res.text)

    def test_run_variant_stamps_payoff_variant_name_in_rows(self) -> None:
        # The radar plot's S_P axis needs a stable per-row tag identifying
        # which variant produced the row; this round-trips it through
        # engine validation and the results processor.
        created = self.client.post(
            "/api/configurations",
            json=_group_body(
                "Tag",
                [
                    {"axis": "payoffMatrix", "name": "harsh", "value": _make_pd_matrix(8)},
                ],
            ),
        ).json()
        res = self.client.post(
            f"/api/configurations/{created['id']}/run",
            params={"demo_mode": "true", "variant": "harsh"},
        )
        self.assertEqual(res.status_code, 200, res.text)
        rows = res.json()["rows"]
        self.assertGreater(len(rows), 0)
        for row in rows:
            self.assertEqual(row["payoff_variant_name"], "harsh")

    def test_run_unknown_variant_errors(self) -> None:
        created = self.client.post(
            "/api/configurations",
            json=_group_body(
                "Sweep",
                [
                    {"axis": "payoffMatrix", "name": "one", "value": _make_pd_matrix(2)},
                ],
            ),
        ).json()
        res = self.client.post(
            f"/api/configurations/{created['id']}/run",
            params={"demo_mode": "true", "variant": "ghost"},
        )
        self.assertEqual(res.status_code, 400, res.text)

    # ---- run-batch fans out groups to all their variants ----

    def test_run_batch_expands_a_group_to_each_variant(self) -> None:
        created = self.client.post(
            "/api/configurations",
            json=_group_body(
                "Sweep",
                [
                    {"axis": "payoffMatrix", "name": "mild", "value": _make_pd_matrix(2)},
                    {"axis": "payoffMatrix", "name": "harsh", "value": _make_pd_matrix(5)},
                    {"axis": "payoffMatrix", "name": "extra", "value": _make_pd_matrix(8)},
                ],
            ),
        ).json()
        res = self.client.post(
            "/api/configurations/run-batch",
            json={
                "configuration_ids": [created["id"]],
                "demo_mode": True,
                "iterations": 1,
            },
        )
        self.assertEqual(res.status_code, 200, res.text)
        results = res.json()["results"]
        # One run-row per variant, all carrying the parent configuration_id.
        self.assertEqual(len(results), 3)
        variants = sorted(r["variant"] for r in results)
        self.assertEqual(variants, ["extra", "harsh", "mild"])
        for r in results:
            self.assertIn("run_id", r)


if __name__ == "__main__":
    unittest.main()
