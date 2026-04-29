"""Shared pytest fixtures for the FAIRGAME test suite.

The fixture registered here installs a deterministic fake connector for every
model name the test configurations reference. This means the unit test suite
does not require live LLM credentials.

Tests that genuinely need a live model can opt out by setting the
``FAIRGAME_LIVE_LLM=1`` env var, in which case the fake is not registered.
"""

from __future__ import annotations

import os
import re
from typing import List

import pytest

from src.llm_connectors import register_model
from src.llm_connectors.abstract_connector import AbstractConnector

# Model names referenced by configs in unit_tests/config and resources/config.
_TEST_MODEL_NAMES: List[str] = [
    "Claude35Sonnet",
    "Claude4Sonnet",
    "MistralLarge",
    "OpenAIGPT4o",
    "OpenAIGPT4oMini",
    "OpenAIGPTo",  # historical alias used in test fixtures
]


class _DeterministicFakeConnector(AbstractConnector):
    """Inspects the prompt for likely strategy labels and returns the first one.

    Strategy is twofold:
    1. Try to extract labels from a "Choose between A and B" / "between A et B" /
       "Choisissez entre A et B" sentence — covers the templates we ship.
    2. Fall back to a small list of well-known English labels so fixtures that
       don't contain such a sentence still parse successfully.
    """

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

    def __init__(self, provider_model: str = "fake") -> None:
        super().__init__()
        self.provider_model = provider_model

    def _send_prompt(self, prompt: str) -> str:
        # Recognise the belief-elicitation prompt and return a valid JSON.
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
        return "JSON" in prompt and "probability" in prompt.lower() or "predict" in prompt.lower()

    def _fake_belief_json(self, prompt: str) -> str:
        # Pull the labels out of the JSON example in the prompt; if that
        # fails fall back to the choose-style match.
        labels = re.findall(r'"([^"]+)":\s*0?\.\d+', prompt)
        if len(labels) < 2:
            match = self._CHOICE_PATTERN.search(prompt)
            if match:
                labels = [match.group(1), match.group(2)]
        if len(labels) < 2:
            labels = list(self.KNOWN_LABELS[:2])
        # Slight asymmetry so Brier != 0 in tests.
        return f'{{"{labels[0]}": 0.7, "{labels[1]}": 0.3}}'


@pytest.fixture(scope="session", autouse=True)
def _install_fake_llm_connector():
    """Replace every test-referenced model with the deterministic fake."""
    if os.getenv("FAIRGAME_LIVE_LLM") == "1":
        yield
        return

    for name in _TEST_MODEL_NAMES:
        register_model(name, _DeterministicFakeConnector, "fake")
    yield
