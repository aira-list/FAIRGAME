"""Deterministic, offline LLM connector used by the test suite.

Every LLM call is answered by this in-process fake: it inspects the prompt and
returns a plausible, deterministic response (a strategy label, a belief-
distribution JSON, or a monitoring decision), so games run to completion without
provider API keys or network access. ``unit_tests/conftest.py`` registers this
class (via :func:`src.llm_connectors.register_model`) for the model names that
test configurations reference.

It is intentionally *not* a language model: it pattern-matches the prompt.
That is enough to drive the engine end-to-end for the deterministic suite.
"""

from __future__ import annotations

import re

from src.llm_connectors.abstract_connector import AbstractConnector


class FakeLLMConnector(AbstractConnector):
    """Answers prompts deterministically, offline — no network, no API key."""

    KNOWN_LABELS = (
        "Cooperate",
        "Betray",
        "OptionA",
        "OptionB",
        "Volunteer",
        "Defect",
    )

    # The "Choose between …" clause, captured up to the sentence end. Kept
    # deliberately loose (``.+?``) so it tolerates multi-word, quoted, and 3+
    # option labels — not just single unquoted words.
    _CHOICE_CLAUSE = re.compile(
        r"(?:between|entre|zwischen|tra|między|tussen)\s+(.+?)(?:[.\n]|$)",
        re.IGNORECASE,
    )
    # Separators between options: commas and the localized "and"/"or".
    _OPTION_SEP = re.compile(r"\s*,\s*|\s+(?:and|or|et|ou|und|oder|e|o|en|i)\s+", re.IGNORECASE)

    def __init__(self, provider_model: str = "fake") -> None:
        super().__init__()
        # Kept for parity with real connectors / logging; never used to call out.
        self.provider_model = provider_model
        self.max_tokens = None
        self.temperature = None

    def send_prompt(self, prompt: str) -> str:
        # Bypass the retry / throttle / cross-process rate-limiter machinery in
        # AbstractConnector.send_prompt: this is an in-process deterministic
        # fake with no network, so those add pure latency and — worse — would
        # consume the shared provider rate-limit budget and advance the global
        # throttle clock, penalising concurrent *real* runs. Answer directly.
        return self._send_prompt(prompt)

    def _send_prompt(self, prompt: str) -> str:
        # Trust monitoring-decision prompt: always LOOK so the cost/gating path
        # is exercised.
        if "LOOK" in prompt and "NO_LOOK" in prompt:
            return "LOOK"
        # Belief-elicitation prompt: return a valid, slightly asymmetric JSON.
        if self._is_belief_prompt(prompt):
            return self._fake_belief_json(prompt)
        choices = self._extract_choices(prompt)
        if choices:
            return choices[0]
        for label in self.KNOWN_LABELS:
            if re.search(rf"\b{re.escape(label)}\b", prompt):
                return label
        return self.KNOWN_LABELS[0]

    def _extract_choices(self, prompt: str) -> list[str]:
        """Pull the option labels out of a "Choose between …" clause.

        Handles multi-word labels ("Stay Silent"), quoted labels, and 3+
        options ("Rock, Paper and Scissors") — returning them in order.
        """
        match = self._CHOICE_CLAUSE.search(prompt)
        if not match:
            return []
        segment = match.group(1)
        # If the options are quoted, take the quoted tokens directly (robust
        # for multi-word labels); otherwise split on comma / "and" / "or".
        quoted = re.findall(r"['\"]([^'\"]+)['\"]", segment)
        parts = quoted if quoted else self._OPTION_SEP.split(segment)
        return [p.strip().strip("'\"").strip() for p in parts if p and p.strip()]

    @staticmethod
    def _is_belief_prompt(prompt: str) -> bool:
        return "JSON" in prompt and ("probability" in prompt.lower() or "predict" in prompt.lower())

    def _fake_belief_json(self, prompt: str) -> str:
        labels = re.findall(r'"([^"]+)":\s*0?\.\d+', prompt)
        if len(labels) < 2:
            labels = self._extract_choices(prompt)
        if len(labels) < 2:
            labels = list(self.KNOWN_LABELS[:2])
        # Slight asymmetry so Brier scores aren't trivially zero.
        return f'{{"{labels[0]}": 0.7, "{labels[1]}": 0.3}}'
