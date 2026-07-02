"""Engine wrapper: FairGameFactory bridge."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from src.fairgame_factory import FairGameFactory
from src.results_processing.results_processor import ResultsProcessor
from src.template_translation.template_translator import TemplateTranslator


class FairGameEngine:
    """Wraps :class:`FairGameFactory` and the results processor."""

    def __init__(
        self,
        translator: TemplateTranslator | None = None,
    ) -> None:
        self.results_processor = ResultsProcessor()
        self._translator = translator
        self._translator_model = os.getenv("FAIRGAME_TRANSLATOR_MODEL", "OpenAIGPT4o")

    @property
    def template_translator(self) -> TemplateTranslator:
        if self._translator is None:
            self._translator = TemplateTranslator(self._translator_model)
        return self._translator

    def create_and_run_games(
        self,
        config: dict[str, Any],
        progress_cb: Callable[[dict[str, Any]], None] | None = None,
    ) -> list[dict[str, Any]]:
        if not isinstance(config, dict):
            raise ValueError("Request body must be a JSON object.")
        self._validate_llms_config(config)
        outcomes = FairGameFactory().create_and_run_games(config, progress_cb=progress_cb)
        df = self.results_processor.process(outcomes)
        return df.to_dict(orient="records")

    def count_games(self, config: dict[str, Any]) -> int:
        """Number of games one ``create_and_run_games(config)`` call will run.

        Builds the permutation set (cheap — no LLM calls) without running it,
        so the web layer can size a progress bar before a run starts. Accounts
        for the multi-seed sweep (``seedCount``/``seeds``), which reruns the
        whole set once per seed.
        """
        if not isinstance(config, dict):
            raise ValueError("Request body must be a JSON object.")
        factory = FairGameFactory()
        processed = factory.io_manager.process_and_validate_configuration(config)
        seeds = factory.resolve_seeds(processed)
        n_seeds = max(1, len(seeds))
        seed = seeds[0] if seeds else None
        if seed is not None:
            processed = {**processed, "seed": seed}
        factory.create_games(processed, resolved_seed=seed)
        return len(factory.games) * n_seeds

    @staticmethod
    def _validate_llms_config(config: dict[str, Any]) -> None:
        if "llms" in config:
            if not isinstance(config["llms"], (list, dict)):
                raise ValueError(
                    "'llms' must be a list of model names or a dict {agent_name: model}."
                )
        elif "llm" in config:
            if not isinstance(config["llm"], str) or not config["llm"]:
                raise ValueError("'llm' must be a non-empty string.")
        else:
            raise ValueError("Configuration must include 'llm' or 'llms'.")


# Process-wide engine singleton, constructed on first use via ``get_engine()``.
# Deferred so that importing this module (e.g. when route modules are imported
# during test collection or app boot) does not read env as an import-time side
# effect.
_engine: FairGameEngine | None = None


def get_engine() -> FairGameEngine:
    """Return the process-wide :class:`FairGameEngine`, building it on first use."""
    global _engine
    if _engine is None:
        _engine = FairGameEngine()
    return _engine
