"""Tests for :mod:`src.template_translation.template_translator`.

Translation tests that genuinely need an LLM are skipped unless
``FAIRGAME_LIVE_LLM=1`` is set, since the deterministic fake registered in
``conftest.py`` cannot reasonably produce a translation.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path

import pytest

from src.io_managers.io_manager import IoManager
from src.template_translation.template_translator import TemplateTranslator

LLM = "OpenAIGPT4o"
CONFIG_PATH = Path("unit_tests/game_templates")
BODY_FILEPATH = CONFIG_PATH / "prisoner_dilemma_en.txt"


def _live_llm_required() -> None:
    if os.getenv("FAIRGAME_LIVE_LLM") != "1":
        pytest.skip("Live LLM not available; set FAIRGAME_LIVE_LLM=1 to run.")


class TestTranslation(unittest.TestCase):
    """Tests covering the placeholder-preserving translation pipeline."""

    def setUp(self) -> None:
        self.io_manager = IoManager()
        self._translator = None

    @property
    def template_translator(self) -> TemplateTranslator:
        if self._translator is None:
            self._translator = TemplateTranslator(LLM)
        return self._translator

    def _load_template(self, filepath: Path) -> str:
        with filepath.open("r", encoding="utf-8") as file:
            return file.read()

    def test_translation_from_en_to_fr(self) -> None:
        _live_llm_required()
        body_template = self._load_template(BODY_FILEPATH)
        fr_translation = self.template_translator.translate(
            body_template, "fr", cosine_threshold=0.6
        )
        self.assertIsInstance(fr_translation, str)
        self.assertGreater(len(fr_translation), 0)

    def test_all_placeholders_preserved(self) -> None:
        base_text = (
            "this is the base text with {x} placeholders and {y} characters and {y} words"
        )
        bugged_texts = [
            "this is a bugged text with {y} placeholders and {y} characters and {x} words",
            "this is a bugged text with {x} placeholders and {y} characters",
            "this is a bugged text with {x} placeholders and {y} characters and {z} words",
        ]
        correct_text = (
            "this is a good text with {x} placeholders and {y} characters and {y} words"
        )

        for bugged_text in bugged_texts:
            with self.assertRaises(ValueError):
                self.template_translator.check_all_placeholders_preserved(
                    base_text, bugged_text
                )

        # Should not raise.
        self.template_translator.check_all_placeholders_preserved(base_text, correct_text)

    def test_cosine_similarity_failure(self) -> None:
        _live_llm_required()
        original_text = "Hello, world!"
        with self.assertRaises(ValueError):
            self.template_translator.translate(
                original_text, "fr", cosine_threshold=1.0
            )


if __name__ == "__main__":
    unittest.main()
