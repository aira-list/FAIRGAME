"""Tests for the FastAPI app at ``web_api.main``.

Uses Starlette's ``TestClient`` so the suite stays in-process and free
of any network or live LLM.

Coverage:

* /api/health returns the expected envelope.
* /api/configurations/{id}/run runs the offline baseline config end-to-end
  and persists to results/web/<id>.
* /api/runs (GET list) reflects the new run.
* /api/runs/{id} returns the persisted rows.
"""

from __future__ import annotations

import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from unit_tests.support import RESOURCES_SKIP_REASON, resources_available

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TestFairgameWeb(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Isolate BOTH stores: RUNS_DIR so we never touch the user-visible
        # results/web/, and DATA_DIR so the library is the pristine
        # starter-library seed set rather than the developer's live library
        # (which previously made the suite break if a seed config had been
        # deleted via the UI). The shipped seeds include the offline
        # baseline-tournament config these tests run.
        from unit_tests.support import isolated_storage_dirs
        from web_api.main import app

        cls._dirs_cm = isolated_storage_dirs(prefix="fg_web_")
        cls._dirs = cls._dirs_cm.__enter__()
        cls._tmp = str(cls._dirs["runs"])
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._dirs_cm.__exit__(None, None, None)

    def test_health_envelope(self) -> None:
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["status"], "OK")

    def test_settings_community_url_defaults_empty(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("FAIRGAME_COMMUNITY_URL", None)
            body = self.client.get("/api/settings").json()
        self.assertEqual(body["community_url"], "")

    def test_settings_community_url_from_env(self) -> None:
        with patch.dict(os.environ, {"FAIRGAME_COMMUNITY_URL": "https://fairgame.example.org"}):
            body = self.client.get("/api/settings").json()
        self.assertEqual(body["community_url"], "https://fairgame.example.org")

    def test_run_flow_offline_config_round_trips(self) -> None:
        # The offline baseline tournament runs with no API keys.
        res = self.client.post("/api/configurations/seed_cfg_pd_baseline_tournament/run")
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertIn("id", body)
        self.assertIsInstance(body["rows"], list)
        self.assertGreater(len(body["rows"]), 0)
        # Per-run metadata must be persisted on disk.
        run_dir = Path(self._tmp) / body["id"]
        self.assertTrue((run_dir / "metadata.json").is_file())
        self.assertTrue((run_dir / "results.csv").is_file())

        # The list endpoint reflects it.
        listed = self.client.get("/api/runs").json()["runs"]
        self.assertIn(body["id"], [r["id"] for r in listed])

        # Detail endpoint returns rows.
        detail = self.client.get(f"/api/runs/{body['id']}").json()
        self.assertEqual(detail["id"], body["id"])
        self.assertGreater(len(detail["rows"]), 0)

    def test_run_without_config_errors_400(self) -> None:
        res = self.client.post("/api/runs", json={})
        self.assertEqual(res.status_code, 400, res.text)

    def test_dashboard_endpoint_returns_relevant_sections(self) -> None:
        run_id = self.client.post("/api/configurations/seed_cfg_pd_baseline_tournament/run").json()[
            "id"
        ]
        res = self.client.get(f"/api/runs/{run_id}/dashboard")
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertIn("sections", body)
        ids = {c["id"] for s in body["sections"] for c in s["charts"]}
        self.assertIn("outcome_mix", ids)

    def test_dashboard_endpoint_404_for_unknown_run(self) -> None:
        res = self.client.get("/api/runs/does-not-exist/dashboard")
        self.assertEqual(res.status_code, 404, res.text)

    def test_compare_endpoint_returns_cross_model_spec(self) -> None:
        rid = self.client.post("/api/configurations/seed_cfg_pd_baseline_tournament/run").json()[
            "id"
        ]
        res = self.client.post("/api/compare", json={"run_ids": [rid]})
        self.assertEqual(res.status_code, 200, res.text)
        ids = {c["id"] for s in res.json()["sections"] for c in s["charts"]}
        # Always-present comparison charts; the robustness radar only appears
        # when the selection spans enough axes (languages/payoffs/rounds).
        self.assertIn("compare_payoff", ids)

    def test_root_serves_spa(self) -> None:
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("FAIRGAME", res.text)


# --- Demo-configuration fixtures -------------------------------------------
# FAIRGAME ships with an empty library (see web_api/seeds.py). These five
# configurations — one per canonical 2x2 game plus the ToM and tournament
# showcases — used to be the shipped seeds; they now live here purely as a
# *test fixture* so the end-to-end smoke below stays independent of whatever
# the product chooses to seed.
_PD_MATRIX = {
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
}
_SH_MATRIX = {
    "weights": {"weight1": 4, "weight2": 1, "weight3": 0, "weight4": 2},
    "strategies": {"en": {"strategy1": "Stag", "strategy2": "Hare"}},
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


def _demo_template(tpl_id, game_type_id, body):
    return {
        "id": tpl_id,
        "game_type_id": game_type_id,
        "variation": "classic",
        "language": "en",
        "body": body,
        "source_template_id": None,
        "source_language": None,
        "created_at": "2026-04-29T20:00:00",
    }


def _demo_config(cid, name, game_type_id, languages, game_config):
    full = {
        "agentsCommunicate": False,
        "allAgentPermutations": False,
        "stopGameWhen": [],
        **game_config,
    }
    return {
        "id": cid,
        "name": name,
        "game_type_id": game_type_id,
        "variation": "classic",
        "languages": languages,
        "game_config": full,
        "created_at": "2026-04-29T20:00:00",
    }


DEMO_CONFIGS = [
    _demo_config(
        "cfg_pd_basic",
        "1. Basic Prisoner's Dilemma — minimal",
        "gt_pd",
        ["en"],
        {
            "nRounds": 5,
            "nRoundsIsKnown": True,
            "agents": {
                "names": ["agent1", "agent2"],
                "personalities": {"en": ["cooperative", "selfish"]},
                "llmServices": ["OpenAIGPT4o", "OpenAIGPT4o"],
                "opponentPersonalityProb": [0, 0],
            },
            "payoffMatrix": _PD_MATRIX,
            "llm": "OpenAIGPT4o",
            "seed": 42,
            "tomOrder": 0,
        },
    ),
    _demo_config(
        "cfg_pd_tom",
        "2. PD with Theory of Mind",
        "gt_pd",
        ["en"],
        {
            "nRounds": 5,
            "nRoundsIsKnown": True,
            "elicitBeliefs": True,
            "tomOrder": 2,
            "reputationWindow": 3,
            "reputationApplies": True,
            "agents": {
                "names": ["agent1", "agent2"],
                "personalities": {"en": ["cooperative", "selfish"]},
                "llmServices": ["OpenAIGPT4o", "OpenAIGPT4o"],
                "opponentPersonalityProb": [0.7, 0.7],
            },
            "payoffMatrix": _PD_MATRIX,
            "llm": "OpenAIGPT4o",
            "baselineSemantics": {"cooperate": "strategy1", "defect": "strategy2"},
            "seed": 42,
        },
    ),
    _demo_config(
        "cfg_pd_tournament",
        "3. Round-robin tournament",
        "gt_pd",
        ["en"],
        {
            "nRounds": 10,
            "nRoundsIsKnown": True,
            "tournament": {"enabled": True, "mode": "round_robin", "symmetric": True},
            "agents": {
                "names": ["llm_player", "tit_for_tat", "always_defect"],
                "personalities": {"en": ["neutral", "neutral", "neutral"]},
                "llmServices": ["OpenAIGPT4o", "baseline:tit_for_tat", "baseline:always_defect"],
                "opponentPersonalityProb": [0, 0, 0],
            },
            "payoffMatrix": _PD_MATRIX,
            "llm": "OpenAIGPT4o",
            "baselineSemantics": {"cooperate": "strategy1", "defect": "strategy2"},
            "discountFactor": 0.95,
            "seed": 42,
        },
    ),
    _demo_config(
        "cfg_sh_advanced",
        "4. Stag Hunt — discount + auto Nash + Fehr-Schmidt",
        "gt_sh",
        ["en"],
        {
            "nRounds": 4,
            "nRoundsIsKnown": True,
            "discountFactor": 0.9,
            "continuationProbability": 1.0,
            "equilibria": "auto",
            "paretoOptimalSum": 8.0,
            "agents": {
                "names": ["agent1", "agent2"],
                "personalities": {"en": ["bold", "cautious"]},
                "llmServices": ["OpenAIGPT4o", "OpenAIGPT4o"],
                "opponentPersonalityProb": [0.3, 0.3],
            },
            "payoffMatrix": _SH_MATRIX,
            "utility": {"type": "FehrSchmidt", "alpha": 0.4, "beta": 0.6},
            "llm": "OpenAIGPT4o",
            "seed": 7,
            "seedCount": 3,
        },
    ),
    _demo_config(
        "cfg_pd_perms",
        "5. PD permutation sweep",
        "gt_pd",
        ["en"],
        {
            "nRounds": 3,
            "nRoundsIsKnown": True,
            "allAgentPermutations": True,
            "agents": {
                "names": ["agent1", "agent2"],
                "personalities": {"en": ["cooperative", "selfish", "neutral"]},
                "llmServices": ["OpenAIGPT4o", "OpenAIGPT4o"],
                "opponentPersonalityProb": [0, 0.5, 1],
            },
            "payoffMatrix": _PD_MATRIX,
            "llm": "OpenAIGPT4o",
            "seed": 11,
        },
    ),
]


@unittest.skipUnless(resources_available(), RESOURCES_SKIP_REASON)
class TestSeedConfigurationsRunEndToEnd(unittest.TestCase):
    """End-to-end smoke for every example Configuration.

    For each fixture configuration (one per canonical 2x2 game plus the
    ToM and tournament showcases), POST /api/configurations/{id}/run and
    verify the engine returns a non-empty rows payload
    with the columns the Results page expects to render. This catches
    integration-level breakage: the template can't be resolved, the
    payoff matrix doesn't validate, the engine's permutation expander
    can't handle the shape, the result processor changed its column
    contract, etc.

    The configs are seeded into an isolated temp library so the test is
    independent of the shipped starter library. The conftest fake LLM
    connector keeps the test in-process — no live LLM calls.
    """

    EXPECTED_CONFIG_IDS = [c["id"] for c in DEMO_CONFIGS]

    @classmethod
    def setUpClass(cls) -> None:
        import tempfile

        cls._tmp = tempfile.mkdtemp(prefix="fg_seedrun_")
        cls._data_tmp = tempfile.mkdtemp(prefix="fg_seeddata_")
        from web_api import storage
        from web_api.main import app

        cls._real_runs_dir = storage.RUNS_DIR
        cls._real_data_dir = storage.DATA_DIR
        storage.RUNS_DIR = Path(cls._tmp)
        storage.DATA_DIR = Path(cls._data_tmp)
        # Seed the fixture configs + the templates they resolve against into
        # the isolated library, replacing any starter-library seeds.
        gt = storage.RESOURCES_DIR / "game_templates"
        storage.save_store("configurations", list(DEMO_CONFIGS))
        storage.save_store(
            "templates",
            [
                _demo_template("tpl_pd", "gt_pd", (gt / "prisoner_dilemma_tom_en.txt").read_text()),
                _demo_template("tpl_sh", "gt_sh", (gt / "stag_hunt_en.txt").read_text()),
            ],
        )
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        from web_api import storage

        storage.RUNS_DIR = cls._real_runs_dir
        storage.DATA_DIR = cls._real_data_dir
        for tmp in (cls._tmp, cls._data_tmp):
            if tmp:
                shutil.rmtree(tmp, ignore_errors=True)

    def test_starter_library_seeds_are_coherent(self) -> None:
        """The shipped starter library loads and is internally consistent."""
        from web_api import seeds, storage

        for name, items in (
            ("game_types", seeds.SEED_GAME_TYPES),
            ("templates", seeds.SEED_TEMPLATES),
            ("configurations", seeds.SEED_CONFIGURATIONS),
        ):
            self.assertGreater(len(items), 0, f"{name} seed list is empty")
            ids = [it.get("id") for it in items]
            self.assertNotIn(None, ids, f"{name}: entry missing an id")
            self.assertEqual(len(ids), len(set(ids)), f"{name}: duplicate ids")
            self.assertEqual(storage._seed_data(name), items)

        # Configurations and templates must reference shipped game types.
        gt_ids = {gt["id"] for gt in seeds.SEED_GAME_TYPES}
        for tpl in seeds.SEED_TEMPLATES:
            self.assertIn(tpl.get("game_type_id"), gt_ids, tpl.get("id"))
        for cfg in seeds.SEED_CONFIGURATIONS:
            self.assertIn(cfg.get("game_type_id"), gt_ids, cfg.get("id"))

    def test_each_seed_configuration_runs(self) -> None:
        """Each seed config runs to completion and produces sensible rows."""
        for cid in self.EXPECTED_CONFIG_IDS:
            with self.subTest(configuration=cid):
                res = self.client.post(
                    f"/api/configurations/{cid}/run",
                )
                self.assertEqual(res.status_code, 200, res.text)
                body = res.json()
                self.assertIn("id", body)
                self.assertIsInstance(body["rows"], list)
                self.assertGreater(
                    len(body["rows"]),
                    0,
                    f"{cid}: engine returned zero rows",
                )
                # Every row should describe at least one game with two
                # named agents and per-round strategy lists.
                first = body["rows"][0]
                for column in (
                    "game_id",
                    "language",
                    "agent1_name",
                    "agent2_name",
                    "agent1_strategies",
                    "agent2_strategies",
                ):
                    self.assertIn(
                        column,
                        first,
                        f"{cid}: missing column {column!r} in row 0",
                    )


if __name__ == "__main__":
    unittest.main()
