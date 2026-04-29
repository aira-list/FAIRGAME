"""Deterministic in-process LLM used when *Demo mode* is on in the GUI.

The real LLM connectors (OpenAI / Anthropic / Mistral) call paid APIs.
For preview / demo / no-credentials runs we install a fake connector that
inspects the prompt for known strategy labels and returns a sensible
canonical response.

State is kept in module globals so toggling demo mode is trivially
reversible: the original ``MODEL_PROVIDER_MAP`` is captured at import time
and restored when the user turns demo mode off.
"""

from __future__ import annotations

import re
from typing import List

from src.llm_connectors import llm_factory_connector
from src.llm_connectors.abstract_connector import AbstractConnector


# Snapshot the original registry so we can roll back from demo to live.
_ORIGINAL_MAP = dict(llm_factory_connector.MODEL_PROVIDER_MAP)
_DEMO_INSTALLED = False


class _DemoConnector(AbstractConnector):
    """Inspects prompts and returns a canonical response.

    * On a belief-elicitation prompt (containing "JSON" + "predict" /
      "probability"), returns a JSON distribution.
    * On a choose-style prompt ("between A and B"), returns the first label.
    * Otherwise returns the first known label that appears in the prompt.
    """

    KNOWN_LABELS = ("Cooperate", "Defect", "OptionA", "OptionB", "Volunteer", "Betray")
    _CHOICE_PATTERN = re.compile(
        r"(?:between|entre|zwischen|tra|między|tussen)\s+([\wÀ-ÿ]+)\s+(?:and|et|und|e|i|en)\s+([\wÀ-ÿ]+)",
        re.IGNORECASE,
    )

    def __init__(self, provider_model: str = "demo") -> None:
        super().__init__()
        self.provider_model = provider_model

    def _send_prompt(self, prompt: str) -> str:
        if self._is_belief_prompt(prompt):
            return self._belief_json(prompt)
        match = self._CHOICE_PATTERN.search(prompt)
        if match:
            return match.group(1)
        for label in self.KNOWN_LABELS:
            if re.search(rf"\b{re.escape(label)}\b", prompt):
                return label
        return self.KNOWN_LABELS[0]

    @staticmethod
    def _is_belief_prompt(prompt: str) -> bool:
        return "JSON" in prompt and (
            "predict" in prompt.lower() or "probability" in prompt.lower()
        )

    def _belief_json(self, prompt: str) -> str:
        labels = re.findall(r'"([^"]+)":\s*0?\.\d+', prompt)
        if len(labels) < 2:
            match = self._CHOICE_PATTERN.search(prompt)
            if match:
                labels = [match.group(1), match.group(2)]
        if len(labels) < 2:
            labels = list(self.KNOWN_LABELS[:2])
        return f'{{"{labels[0]}": 0.7, "{labels[1]}": 0.3}}'


_TARGET_MODELS: List[str] = [
    "Claude35Sonnet",
    "Claude4Sonnet",
    "MistralLarge",
    "OpenAIGPT4o",
    "OpenAIGPT4oMini",
]


def install_demo_connector() -> None:
    """Replace every shipped model with the deterministic fake."""
    global _DEMO_INSTALLED
    for name in _TARGET_MODELS:
        llm_factory_connector.MODEL_PROVIDER_MAP[name] = (
            (lambda cls=_DemoConnector: cls),
            "demo",
        )
    _DEMO_INSTALLED = True


def restore_real_connectors() -> None:
    """Roll back the registry to the entries captured at import time."""
    global _DEMO_INSTALLED
    llm_factory_connector.MODEL_PROVIDER_MAP.clear()
    llm_factory_connector.MODEL_PROVIDER_MAP.update(_ORIGINAL_MAP)
    _DEMO_INSTALLED = False


def is_demo_active() -> bool:
    return _DEMO_INSTALLED


def set_demo_mode(enabled: bool) -> None:
    """Idempotent toggle."""
    if enabled and not _DEMO_INSTALLED:
        install_demo_connector()
    elif not enabled and _DEMO_INSTALLED:
        restore_real_connectors()
