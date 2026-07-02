"""Shared pytest fixtures for the FAIRGAME test suite.

* Installs the shipped DemoConnector (offline deterministic fake) for every
  test configurations reference (skip with ``FAIRGAME_LIVE_LLM=1``).
"""

from __future__ import annotations

import os

import pytest

from src.llm_connectors import register_model
from src.llm_connectors.demo_connector import DemoConnector

# Model names referenced by configs in unit_tests/config and resources/config.
_TEST_MODEL_NAMES: list[str] = [
    "Claude35Sonnet",
    "Claude4Sonnet",
    "MistralLarge",
    "OpenAIGPT4o",
    "OpenAIGPT4oMini",
    "OpenAIGPTo",  # historical alias used in test fixtures
]


@pytest.fixture(scope="session", autouse=True)
def _install_fake_llm_connector():
    """Replace every test-referenced model with the deterministic fake."""
    if os.getenv("FAIRGAME_LIVE_LLM") == "1":
        yield
        return

    for name in _TEST_MODEL_NAMES:
        register_model(name, DemoConnector, "fake")
    yield
