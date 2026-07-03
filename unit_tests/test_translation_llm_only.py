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


class _FakeTranslator(AbstractConnector):
    """A fake LLM that 'translates' by rewriting the quoted source text.

    It reads the quoted sentence out of the translation prompt and returns a
    changed-but-placeholder-preserving version, plus it records the prompt so
    tests can assert what the translator sent.
    """

    last_prompt: str = ""

    def __init__(self, provider_model: str = "fake-translate") -> None:
        super().__init__()
        self.provider_model = provider_model

    def _send_prompt(self, prompt: str) -> str:
        _FakeTranslator.last_prompt = prompt
        match = re.search(r'"(.*)"', prompt, re.DOTALL)
        text = match.group(1) if match else prompt
        return f"Translation: TRADUIT {text}"


class _EchoTranslator(AbstractConnector):
    """A fake LLM that echoes the source text verbatim (the failure mode where
    a model 'translates' French to Italian by returning the French)."""

    def __init__(self, provider_model: str = "echo-translate") -> None:
        super().__init__()
        self.provider_model = provider_model

    def _send_prompt(self, prompt: str) -> str:
        match = re.search(r'"(.*)"', prompt, re.DOTALL)
        text = match.group(1) if match else prompt
        return f'Translation: "{text}"'


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
        register_model("fake-translate", _FakeTranslator, "fake-translate")
        register_model("echo-translate", _EchoTranslator, "echo-translate")
        register_model("dropper", _PlaceholderDropper, "dropper")

    def test_translate_returns_llm_output_and_preserves_placeholders(self) -> None:
        tr = TemplateTranslator("fake-translate")
        out = tr.translate("Choose {A} or {B}", "fr")
        self.assertIn("{A}", out)
        self.assertIn("{B}", out)
        self.assertIn("TRADUIT", out)

    def test_echoed_source_is_rejected_not_saved(self) -> None:
        # A model that returns the source text unchanged (e.g. French in,
        # French out when Italian was requested) must raise, not pass.
        tr = TemplateTranslator("echo-translate")
        with self.assertRaises(ValueError) as ctx:
            tr.translate("Please choose carefully between {A} and {B} now", "it")
        self.assertIn("unchanged", str(ctx.exception))

    def test_placeholder_dominated_template_may_translate_to_itself(self) -> None:
        # Almost nothing but placeholders: the correct translation IS the
        # source, so an identical answer is accepted, not treated as an echo.
        tr = TemplateTranslator("echo-translate")
        out = tr.translate("{A} vs {B}: {C}?", "it")
        self.assertIn("{A}", out)
        self.assertIn("{C}", out)

    def test_wrapping_quotes_are_stripped(self) -> None:
        tr = TemplateTranslator("fake-translate")
        self.assertEqual(tr._strip_wrapping_quotes('"Bonjour {A}"'), "Bonjour {A}")
        self.assertEqual(tr._strip_wrapping_quotes("“Ciao {A}”"), "Ciao {A}")
        self.assertEqual(tr._strip_wrapping_quotes("No quotes {A}"), "No quotes {A}")

    def test_source_language_is_named_in_the_prompt(self) -> None:
        tr = TemplateTranslator("fake-translate")
        tr.translate("Choisis {A} ou {B}", "it", source_lang_code="fr")
        self.assertIn("written in French", _FakeTranslator.last_prompt)

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
