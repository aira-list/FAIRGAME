"""Tests for the unified :mod:`src.llm_connectors` factory."""

from __future__ import annotations

import os
import unittest
from unittest import mock

from src.llm_connectors import (
    ChatModelFactory,
    MODEL_PROVIDER_MAP,
    execute_prompt,
    register_model,
)
from src.llm_connectors.abstract_connector import AbstractConnector


class _RecordingConnector(AbstractConnector):
    """Connector that records prompts and replies with a canned response."""

    def __init__(self, provider_model: str = "rec-1") -> None:
        super().__init__()
        self.provider_model = provider_model
        self.calls: list[str] = []
        self.reply = "ok"

    def _send_prompt(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self.reply


class _FlakyConnector(AbstractConnector):
    """Fails ``fail_count`` times then succeeds — verifies retry behaviour."""

    RETRYABLE_EXCEPTIONS = (RuntimeError,)

    def __init__(self, provider_model: str = "flaky") -> None:
        super().__init__()
        self.provider_model = provider_model
        self.fail_count = 2
        self.attempts = 0

    def _send_prompt(self, prompt: str) -> str:
        self.attempts += 1
        if self.attempts <= self.fail_count:
            raise RuntimeError("transient")
        return "recovered"


class TestChatModelFactory(unittest.TestCase):
    def test_unknown_model_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            ChatModelFactory.get_model("DoesNotExist")

    def test_register_model_and_execute_prompt(self) -> None:
        register_model("Recorder", _RecordingConnector, "rec-test")
        try:
            self.assertIn("Recorder", MODEL_PROVIDER_MAP)
            response = execute_prompt("Recorder", "hello")
            self.assertEqual(response, "ok")
        finally:
            MODEL_PROVIDER_MAP.pop("Recorder", None)

    def test_retries_on_transient_failure(self) -> None:
        # Backoff capped low so the test stays fast.
        with mock.patch.dict(
            os.environ,
            {
                "FAIRGAME_LLM_MAX_ATTEMPTS": "5",
                "FAIRGAME_LLM_BACKOFF_MIN": "0",
                "FAIRGAME_LLM_BACKOFF_MAX": "0",
            },
        ):
            register_model("Flaky", _FlakyConnector, "flaky")
            try:
                self.assertEqual(execute_prompt("Flaky", "ping"), "recovered")
            finally:
                MODEL_PROVIDER_MAP.pop("Flaky", None)

    def test_exhausted_retries_raise(self) -> None:
        class _AlwaysFails(_FlakyConnector):
            def __init__(self, provider_model: str = "x") -> None:
                super().__init__(provider_model)
                self.fail_count = 99

        with mock.patch.dict(
            os.environ,
            {
                "FAIRGAME_LLM_MAX_ATTEMPTS": "2",
                "FAIRGAME_LLM_BACKOFF_MIN": "0",
                "FAIRGAME_LLM_BACKOFF_MAX": "0",
            },
        ):
            register_model("AlwaysFails", _AlwaysFails, "x")
            try:
                with self.assertRaises(RuntimeError):
                    execute_prompt("AlwaysFails", "ping")
            finally:
                MODEL_PROVIDER_MAP.pop("AlwaysFails", None)


if __name__ == "__main__":
    unittest.main()
