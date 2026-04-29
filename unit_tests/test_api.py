"""Tests for the Flask API.

These tests exercise the API in-process via Flask's test client, using the
deterministic fake LLM connector that ``conftest.py`` registers. The legacy
behaviour of spawning a real subprocess and calling OpenAI has been removed
because it required live network access and credentials.
"""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

import pytest

from api import create_app


class TestFairgameAPI(unittest.TestCase):
    """Integration tests for the API endpoints, served via Flask's test client."""

    @classmethod
    def setUpClass(cls) -> None:
        base_dir = Path(__file__).resolve().parent
        cls.config_dir = base_dir / "config"
        cls.template_dir = base_dir / "game_templates"
        cls.config_filepath = cls.config_dir / "prisoner_dilemma_no_template.json"
        cls.template_filepath = cls.template_dir / "prisoner_dilemma_en.txt"

        cls.app = create_app()
        cls.app.testing = True

    def setUp(self) -> None:
        self.client = self.app.test_client()

    def _load_json_config(self, filepath: Path) -> dict:
        return json.loads(filepath.read_text(encoding="utf-8"))

    def _load_text_template(self, filepath: Path) -> str:
        return filepath.read_text(encoding="utf-8")

    def _create_and_run_games(self, config: dict):
        return self.client.post(
            "/create_and_run_games",
            data=json.dumps(config),
            content_type="application/json",
        )

    def test_health_check(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "OK", "message": "Service is running"})

    def test_create_and_run_games(self) -> None:
        config = self._load_json_config(self.config_filepath)
        template_content = self._load_text_template(self.template_filepath)
        config["promptTemplate"] = {"en": template_content}

        response = self._create_and_run_games(config)
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertIsInstance(body, list)
        self.assertGreater(len(body), 0, msg="Expected non-empty results.")

    def test_malformed_template(self) -> None:
        """Providing both 'promptTemplate' and 'templateFilename' is rejected."""
        config = self._load_json_config(self.config_filepath)
        template_content = self._load_text_template(self.template_filepath)
        config["promptTemplate"] = {"en": template_content}
        config["templateFilename"] = "prisoner_dilemma"

        response = self._create_and_run_games(config)
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())

    def test_missing_body_returns_400(self) -> None:
        response = self.client.post("/create_and_run_games", data="", content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())

    @pytest.mark.skipif(
        os.getenv("FAIRGAME_LIVE_LLM") != "1",
        reason="Translation requires a live LLM; set FAIRGAME_LIVE_LLM=1 to run.",
    )
    def test_successful_translation(self) -> None:
        filepath = Path("resources/game_templates") / "prisoner_dilemma_en.txt"
        template = filepath.read_text(encoding="utf-8")
        response = self.client.post(
            "/translate_template",
            data=json.dumps({
                "llm": "OpenAIGPT4o",
                "template": template,
                "lang_to": "fr",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertIn("translated_text", body)
        self.assertIsInstance(body["translated_text"], str)


if __name__ == "__main__":
    unittest.main()
