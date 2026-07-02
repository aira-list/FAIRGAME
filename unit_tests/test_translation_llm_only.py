"""Translation is LLM-only: no sentence-transformers / torch, model selectable.

FAIRGAME used to gate a translation on an embedding cosine-similarity score
computed by ``sentence-transformers`` (which pulls in torch). That heavy
dependency has been removed: translation is now entirely an LLM call plus a
placeholder-preservation check, and the caller picks which LiteLLM model does
the translating.
"""

from __future__ import annotations

import inspect
import re
import unittest

from src.llm_connectors import register_model
from src.llm_connectors.abstract_connector import AbstractConnector
from src.prompting.template_translator import TemplateTranslator


class _EchoTranslator(AbstractConnector):
    """A fake LLM that 'translates' by echoing the source text verbatim.

    It reads the quoted sentence out of the translation prompt and returns it
    prefixed like a real answer, so placeholders survive unchanged.
    """

    def __init__(self, provider_model: str = "echo-translate") -> None:
        super().__init__()
        self.provider_model = provider_model

    def _send_prompt(self, prompt: str) -> str:
        match = re.search(r'"(.*)"', prompt, re.DOTALL)
        text = match.group(1) if match else prompt
        return f"Translation: {text}"


class _PlaceholderDropper(AbstractConnector):
    """A fake LLM whose translation silently drops a placeholder."""

    def __init__(self, provider_model: str = "dropper") -> None:
        super().__init__()
        self.provider_model = provider_model

    def _send_prompt(self, prompt: str) -> str:
        return "Translation: only {A} survived"


class TestTranslatorIsLLMOnly(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        register_model("echo-translate", _EchoTranslator, "echo-translate")
        register_model("dropper", _PlaceholderDropper, "dropper")

    def test_translate_returns_llm_output_and_preserves_placeholders(self) -> None:
        tr = TemplateTranslator("echo-translate")
        out = tr.translate("Choose {A} or {B}", "fr")
        self.assertIn("{A}", out)
        self.assertIn("{B}", out)

    def test_translate_has_no_cosine_threshold_argument(self) -> None:
        sig = inspect.signature(TemplateTranslator.translate)
        self.assertNotIn("cosine_threshold", sig.parameters)

    def test_translator_exposes_no_embedding_machinery(self) -> None:
        tr = TemplateTranslator("echo-translate")
        self.assertFalse(hasattr(tr, "_calculate_cosine_similarity"))
        self.assertFalse(hasattr(tr, "model"))

    def test_placeholder_mismatch_still_rejected(self) -> None:
        tr = TemplateTranslator("dropper")
        with self.assertRaises(ValueError):
            tr.translate("Choose {A} or {B}", "fr")

    def test_module_import_does_not_pull_sentence_transformers(self) -> None:
        import importlib
        import sys

        sys.modules.pop("sentence_transformers", None)
        module = importlib.import_module("src.prompting.template_translator")
        importlib.reload(module)
        self.assertNotIn("sentence_transformers", sys.modules)


if __name__ == "__main__":
    unittest.main()
