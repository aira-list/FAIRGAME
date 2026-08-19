"""Regression tests for web_api hardening fixes.

Covers:

* PUT /api/configurations/{id} preserves ``created_at`` (it used to be
  erased by ``item.clear()`` before the preserve idiom could read it).
* An unknown variation axis fails as 422 at the boundary (POST/PUT
  /api/configurations and /api/import) instead of an unhandled 500.
* AI-translate ignores archived templates when deciding a target language
  "already exists" — an archived copy must not block a re-translate.
* Restoring an archived template 409s when a non-archived template already
  occupies the same (game_type, variation, language) triple.
* ``run_variant_iteration`` folds the iteration index into the seed axis
  with ``combine_seed`` — no overlap with the seedCount sweep, and an
  explicit ``seeds`` list participates instead of being ignored.
"""

from __future__ import annotations

import re
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.llm_connectors import register_model
from src.llm_connectors.abstract_connector import AbstractConnector
from src.utils.rng import combine_seed


def _config_body(name: str, **overrides) -> dict:
    body = {
        "name": name,
        "game_type_id": "gt_fix",
        "variation": "classic",
        "languages": ["en"],
        "game_config": {"nRounds": 1, "seed": 42},
    }
    body.update(overrides)
    return body


def _template(tpl_id: str, language: str, *, archived: bool = False) -> dict:
    return {
        "id": tpl_id,
        "game_type_id": "gt_fix",
        "variation": "classic",
        "language": language,
        "body": "Choose {strategy1} or {strategy2}.",
        "source_template_id": None,
        "source_language": None,
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
        "versions": [],
        "archived": archived,
    }


class _FixesTranslator(AbstractConnector):
    """Rewrites the quoted source (placeholders intact) so translate tests
    exercise the route without tripping the echo guard."""

    def __init__(self, provider_model: str = "echo-fixes") -> None:
        super().__init__()
        self.provider_model = provider_model

    def _send_prompt(self, prompt: str) -> str:
        match = re.search(r'"(.*)"', prompt, re.DOTALL)
        text = match.group(1) if match else prompt
        return f"Translation: XLATE {text}"


class _WebApiFixesBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from unit_tests.support import isolated_storage_dirs
        from web_api.main import app

        cls._dirs_cm = isolated_storage_dirs(prefix="fg_fixes_")
        cls._dirs_cm.__enter__()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._dirs_cm.__exit__(None, None, None)

    def setUp(self) -> None:
        # Blank slates — the starter seeds are irrelevant here and would only
        # add name-collision noise (they are re-topped-up on next access).
        from web_api.storage import save_store

        save_store("configurations", [])
        save_store("templates", [])


class TestUpdatePreservesCreatedAt(_WebApiFixesBase):
    def test_put_keeps_original_created_at(self) -> None:
        created = self.client.post("/api/configurations", json=_config_body("keep-me")).json()
        # Pin created_at to a clearly-past value so "preserved" is
        # distinguishable from "re-stamped within the same second".
        from web_api.storage import edit_store

        with edit_store("configurations") as items:
            next(i for i in items if i["id"] == created["id"])["created_at"] = "2020-02-02T02:02:02"
        res = self.client.put(
            f"/api/configurations/{created['id']}", json=_config_body("keep-me-renamed")
        )
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["created_at"], "2020-02-02T02:02:02")
        self.assertEqual(res.json()["name"], "keep-me-renamed")


class TestUnknownVariationAxisIs422(_WebApiFixesBase):
    def _variants(self, axis: str) -> list[dict]:
        return [{"axis": axis, "name": "v1", "value": {"weights": {}}}]

    def test_post_configuration_rejects_unknown_axis(self) -> None:
        res = self.client.post(
            "/api/configurations",
            json=_config_body("bad-axis", variations=self._variants("nRounds")),
        )
        self.assertEqual(res.status_code, 422)

    def test_put_configuration_rejects_unknown_axis(self) -> None:
        created = self.client.post("/api/configurations", json=_config_body("good")).json()
        res = self.client.put(
            f"/api/configurations/{created['id']}",
            json=_config_body("good", variations=self._variants("agents")),
        )
        self.assertEqual(res.status_code, 422)

    def test_payoff_matrix_axis_still_accepted(self) -> None:
        res = self.client.post(
            "/api/configurations",
            json=_config_body("good-axis", variations=self._variants("payoffMatrix")),
        )
        self.assertEqual(res.status_code, 200, res.text)

    def test_import_rejects_unknown_axis(self) -> None:
        bundle = {
            "fairgame_bundle": "1",
            "configuration": {
                **_config_body("imported"),
                "id": "cfg_x",
                "variations": self._variants("tomOrder"),
            },
        }
        res = self.client.post("/api/import", json=bundle)
        self.assertEqual(res.status_code, 422)


class TestTranslateIgnoresArchivedTemplates(_WebApiFixesBase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        register_model("echo-fixes", _FixesTranslator, "echo-fixes")

    def test_archived_target_does_not_block_translation(self) -> None:
        from web_api.storage import save_store

        save_store(
            "templates",
            [_template("tpl_en", "en"), _template("tpl_fr", "fr", archived=True)],
        )
        res = self.client.post(
            "/api/templates/tpl_en/translate",
            json={"target_languages": ["fr"], "model": "echo-fixes"},
        )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual([t["language"] for t in body["created"]], ["fr"])
        self.assertEqual(body["skipped"], [])

    def test_live_target_still_skipped(self) -> None:
        from web_api.storage import save_store

        save_store(
            "templates",
            [_template("tpl_en", "en"), _template("tpl_fr", "fr")],
        )
        body = self.client.post(
            "/api/templates/tpl_en/translate",
            json={"target_languages": ["fr"], "model": "echo-fixes"},
        ).json()
        self.assertEqual(body["created"], [])
        self.assertEqual(len(body["skipped"]), 1)


class TestRestoreRespectsTripleUniqueness(_WebApiFixesBase):
    def test_restore_409s_when_live_twin_exists(self) -> None:
        from web_api.storage import save_store

        save_store(
            "templates",
            [_template("tpl_old", "en", archived=True), _template("tpl_new", "en")],
        )
        res = self.client.post("/api/templates/tpl_old/restore")
        self.assertEqual(res.status_code, 409)
        # Still archived after the rejected restore.
        items = self.client.get("/api/templates", params={"include_archived": True}).json()[
            "templates"
        ]
        self.assertTrue(next(t for t in items if t["id"] == "tpl_old")["archived"])

    def test_restore_succeeds_without_collision(self) -> None:
        from web_api.storage import save_store

        save_store("templates", [_template("tpl_old", "en", archived=True)])
        res = self.client.post("/api/templates/tpl_old/restore")
        self.assertEqual(res.status_code, 200, res.text)
        self.assertFalse(res.json()["archived"])


class TestIterationSeedFolding(unittest.TestCase):
    """run_variant_iteration derives per-iteration seeds via combine_seed."""

    def _run(self, config: dict, it: int) -> dict:
        from web_api.configurations_lib import ResolvedVariant
        from web_api.library_service import run_variant_iteration

        variant = ResolvedVariant(None, "cfg", config)
        captured: dict = {}

        class _Engine:
            def create_and_run_games(self, cfg, progress_cb=None):
                captured.update(cfg)
                return []

        with (
            patch("web_api.library_service.get_engine", return_value=_Engine()),
            patch("web_api.library_service.save_run"),
        ):
            run_variant_iteration("cid", {"id": "cid"}, variant, it, iterations=3)
        return captured

    def test_iteration_zero_is_byte_identical(self) -> None:
        cfg = {"seed": 42, "seedCount": 3, "nRounds": 1}
        self.assertEqual(self._run(cfg, 0), cfg)

    def test_later_iterations_fold_the_seed(self) -> None:
        got = self._run({"seed": 42, "nRounds": 1}, 2)
        self.assertEqual(got["seed"], combine_seed(42, 2))

    def test_folding_avoids_seedcount_overlap(self) -> None:
        # The old ``seed + it`` made iteration 2 of a seedCount=3 sweep re-run
        # two of iteration 1's child seeds (43, 44). Folded seeds are disjoint.
        base = {"seed": 42, "seedCount": 3}
        it1 = self._run(dict(base), 1)["seed"]
        it2 = self._run(dict(base), 2)["seed"]

        def children(s: int) -> set[int]:  # the engine's seedCount expansion
            return {s + i for i in range(3)}

        self.assertFalse(children(it1) & children(it2))

    def test_explicit_seeds_list_participates(self) -> None:
        got = self._run({"seeds": [7, 8], "nRounds": 1}, 1)
        self.assertEqual(got["seeds"], [combine_seed(7, 1), combine_seed(8, 1)])

    def test_no_seed_stays_untouched(self) -> None:
        got = self._run({"nRounds": 1}, 2)
        self.assertNotIn("seed", got)
        self.assertNotIn("seeds", got)


if __name__ == "__main__":
    unittest.main()
