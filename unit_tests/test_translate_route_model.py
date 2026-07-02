"""The translate endpoint lets the caller choose the translator LLM.

``POST /api/templates/{id}/translate`` accepts an optional ``model`` (any
LiteLLM-resolvable name); ``cosine_threshold`` is gone. ``/api/settings``
advertises the default translator model so the SPA can preselect it.
"""

from __future__ import annotations

import re
import unittest

from fastapi.testclient import TestClient

from src.llm_connectors import register_model
from src.llm_connectors.abstract_connector import AbstractConnector
from web_api.models import TemplateTranslateBody


class _EchoTranslator(AbstractConnector):
    def __init__(self, provider_model: str = "echo-route") -> None:
        super().__init__()
        self.provider_model = provider_model

    def _send_prompt(self, prompt: str) -> str:
        match = re.search(r'"(.*)"', prompt, re.DOTALL)
        text = match.group(1) if match else prompt
        return f"Translation: {text}"


class TestTranslateRequestModel(unittest.TestCase):
    def test_body_accepts_model_and_drops_cosine_threshold(self) -> None:
        fields = TemplateTranslateBody.model_fields
        self.assertIn("model", fields)
        self.assertNotIn("cosine_threshold", fields)
        body = TemplateTranslateBody(target_languages=["fr"], model="litellm:gpt-4o")
        self.assertEqual(body.model, "litellm:gpt-4o")
        # model is optional (falls back to the server default).
        self.assertIsNone(TemplateTranslateBody(target_languages=["fr"]).model)


class TestTranslateRouteEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from unit_tests.support import isolated_storage_dirs
        from web_api.main import app

        register_model("echo-route", _EchoTranslator, "echo-route")
        cls._dirs_cm = isolated_storage_dirs(prefix="fg_translate_")
        cls._dirs = cls._dirs_cm.__enter__()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._dirs_cm.__exit__(None, None, None)

    def test_settings_advertise_default_translator_model(self) -> None:
        body = self.client.get("/api/settings").json()
        self.assertIn("translator_model", body)
        self.assertTrue(body["translator_model"])

    def test_translate_uses_chosen_model(self) -> None:
        templates = self.client.get("/api/templates").json()["templates"]
        english = next(t for t in templates if t["language"] == "en")
        # Pick a target language that isn't already shipped for this variant,
        # so the translation is actually created rather than skipped.
        present = {
            t["language"]
            for t in templates
            if t["game_type_id"] == english["game_type_id"]
            and t["variation"] == english["variation"]
        }
        target = next(c for c in ("sw", "ha", "ro", "uk", "th") if c not in present)
        res = self.client.post(
            f"/api/templates/{english['id']}/translate",
            json={"target_languages": [target], "model": "echo-route"},
        )
        self.assertEqual(res.status_code, 200, res.text)
        payload = res.json()
        # The echo translator preserves the body verbatim, so a French
        # template gets created (no cosine gate to reject the "translation").
        self.assertEqual(len(payload["created"]), 1, payload)
        self.assertEqual(payload["errors"], [])


if __name__ == "__main__":
    unittest.main()
