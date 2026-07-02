"""Deterministic, offline LLM connector powering FAIRGAME's demo mode.

Demo mode lets anyone explore the app — run scenarios, see results, exercise
every phase — without provider API keys and without incurring charges. Every
LLM call is answered by this in-process fake: it inspects the prompt and
returns a plausible, deterministic response (a strategy label, a belief-
distribution JSON, or a monitoring decision), so games run to completion.

It is intentionally *not* a language model: it pattern-matches the prompt.
That is enough to drive the engine end-to-end for demonstration and testing.
This mirrors the fake registered by the unit-test conftest; keep the two in
sync if you change the parsing heuristics.
"""

from __future__ import annotations

import re

from src.llm_connectors.abstract_connector import AbstractConnector


class DemoConnector(AbstractConnector):
    """Answers prompts deterministically, offline — no network, no API key."""

    KNOWN_LABELS = (
        "Cooperate",
        "Betray",
        "OptionA",
        "OptionB",
        "Volunteer",
        "Defect",
    )

    # ``Choose between X and Y``, ``entre X et Y``, ``zwischen X und Y``, ...
    _CHOICE_PATTERN = re.compile(
        r"(?:between|entre|zwischen|tra|między|tussen)\s+([\wÀ-ÿ]+)\s+(?:and|et|und|e|i|en)\s+([\wÀ-ÿ]+)",
        re.IGNORECASE,
    )

    def __init__(self, provider_model: str = "demo") -> None:
        super().__init__()
        # Kept for parity with real connectors / logging; never used to call out.
        self.provider_model = provider_model
        self.max_tokens = None
        self.temperature = None

    def _send_prompt(self, prompt: str) -> str:
        # Trust monitoring-decision prompt: always LOOK so the cost/gating path
        # is exercised in demos.
        if "LOOK" in prompt and "NO_LOOK" in prompt:
            return "LOOK"
        # Belief-elicitation prompt: return a valid, slightly asymmetric JSON.
        if self._is_belief_prompt(prompt):
            return self._fake_belief_json(prompt)
        match = self._CHOICE_PATTERN.search(prompt)
        if match:
            return match.group(1)
        for label in self.KNOWN_LABELS:
            if re.search(rf"\b{re.escape(label)}\b", prompt):
                return label
        return self.KNOWN_LABELS[0]

    @staticmethod
    def _is_belief_prompt(prompt: str) -> bool:
        return "JSON" in prompt and ("probability" in prompt.lower() or "predict" in prompt.lower())

    def _fake_belief_json(self, prompt: str) -> str:
        labels = re.findall(r'"([^"]+)":\s*0?\.\d+', prompt)
        if len(labels) < 2:
            match = self._CHOICE_PATTERN.search(prompt)
            if match:
                labels = [match.group(1), match.group(2)]
        if len(labels) < 2:
            labels = list(self.KNOWN_LABELS[:2])
        # Slight asymmetry so Brier scores aren't trivially zero.
        return f'{{"{labels[0]}": 0.7, "{labels[1]}": 0.3}}'
