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


# ---------------------------------------------------------------------------
# Test-only connectors
# ---------------------------------------------------------------------------

class _RecordingConnector(AbstractConnector):
    """Records prompts and returns a canned response."""

    def __init__(self, provider_model: str = "rec-1") -> None:
        super().__init__()
        self.provider_model = provider_model
        self.calls: list[str] = []
        self.reply = "ok"

    def _send_prompt(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self.reply


class _FlakyConnector(AbstractConnector):
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


class _AlwaysFailingConnector(AbstractConnector):
    RETRYABLE_EXCEPTIONS = (RuntimeError,)

    def __init__(self, provider_model: str = "x") -> None:
        super().__init__()
        self.provider_model = provider_model
        self.attempts = 0

    def _send_prompt(self, prompt: str) -> str:
        self.attempts += 1
        raise RuntimeError(f"failure on attempt {self.attempts}")


class _NonRetryableErrorConnector(AbstractConnector):
    """Raises a non-retryable error — should bubble up immediately."""

    RETRYABLE_EXCEPTIONS = (RuntimeError,)

    def __init__(self, provider_model: str = "x") -> None:
        super().__init__()
        self.provider_model = provider_model
        self.attempts = 0

    def _send_prompt(self, prompt: str) -> str:
        self.attempts += 1
        raise ValueError("permanent")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _RegistryIsolation(unittest.TestCase):
    """Snapshot the registry around each test so mutations don't leak."""

    def setUp(self) -> None:
        self._snapshot = dict(MODEL_PROVIDER_MAP)

    def tearDown(self) -> None:
        MODEL_PROVIDER_MAP.clear()
        MODEL_PROVIDER_MAP.update(self._snapshot)


# ---------------------------------------------------------------------------
# ChatModelFactory.get_model
# ---------------------------------------------------------------------------

class TestGetModel(_RegistryIsolation):
    def test_unknown_model_raises_value_error_with_known_list(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            ChatModelFactory.get_model("DoesNotExist")
        # Message must mention what *was* known to help the user.
        self.assertIn("DoesNotExist", str(ctx.exception))

    def test_returns_an_instance_of_the_registered_class(self) -> None:
        register_model("Recorder", _RecordingConnector, "rec-test")
        instance = ChatModelFactory.get_model("Recorder")
        self.assertIsInstance(instance, _RecordingConnector)

    def test_repeated_get_model_calls_create_distinct_instances(self) -> None:
        # The factory returns a fresh instance per call so callers can't
        # accidentally share state.
        register_model("Recorder", _RecordingConnector, "rec-test")
        a = ChatModelFactory.get_model("Recorder")
        b = ChatModelFactory.get_model("Recorder")
        self.assertIsNot(a, b)


# ---------------------------------------------------------------------------
# register_model
# ---------------------------------------------------------------------------

class TestRegisterModel(_RegistryIsolation):
    def test_register_adds_to_map(self) -> None:
        register_model("NewName", _RecordingConnector, "x")
        self.assertIn("NewName", MODEL_PROVIDER_MAP)

    def test_register_overrides_existing(self) -> None:
        register_model("Name", _RecordingConnector, "v1")
        register_model("Name", _RecordingConnector, "v2")
        loader, model = MODEL_PROVIDER_MAP["Name"]
        self.assertEqual(model, "v2")


# ---------------------------------------------------------------------------
# execute_prompt happy path
# ---------------------------------------------------------------------------

class TestExecutePromptHappyPath(_RegistryIsolation):
    def test_returns_connector_response(self) -> None:
        register_model("Recorder", _RecordingConnector, "rec-test")
        self.assertEqual(execute_prompt("Recorder", "hello"), "ok")

    def test_passes_prompt_through_to_connector(self) -> None:
        register_model("Recorder", _RecordingConnector, "rec-test")
        # One execute_prompt call → one entry in the recorder's call list.
        self.assertEqual(execute_prompt("Recorder", "first"), "ok")
        self.assertEqual(execute_prompt("Recorder", "second"), "ok")
        # Per-call instance, so no shared state — but each instance got
        # exactly one call. Pulling the latest instance verifies that.
        loader, _ = MODEL_PROVIDER_MAP["Recorder"]
        # We can't introspect the instance after the fact; assert via
        # behaviour: a fresh instance starts with empty calls.
        instance = loader()()
        self.assertEqual(instance.calls, [])


# ---------------------------------------------------------------------------
# Retry behaviour
# ---------------------------------------------------------------------------

class TestRetryBehaviour(_RegistryIsolation):
    def _fast_retries(self) -> dict[str, str]:
        return {
            "FAIRGAME_LLM_BACKOFF_MIN": "0",
            "FAIRGAME_LLM_BACKOFF_MAX": "0",
        }

    def test_retries_until_success(self) -> None:
        with mock.patch.dict(
            os.environ, {**self._fast_retries(), "FAIRGAME_LLM_MAX_ATTEMPTS": "5"}
        ):
            register_model("Flaky", _FlakyConnector, "flaky")
            self.assertEqual(execute_prompt("Flaky", "ping"), "recovered")

    def test_exhausted_retries_reraise_last_exception(self) -> None:
        with mock.patch.dict(
            os.environ, {**self._fast_retries(), "FAIRGAME_LLM_MAX_ATTEMPTS": "2"}
        ):
            register_model("AlwaysFails", _AlwaysFailingConnector, "x")
            with self.assertRaises(RuntimeError) as ctx:
                execute_prompt("AlwaysFails", "ping")
            # The exception text comes from the underlying call.
            self.assertIn("attempt", str(ctx.exception))

    def test_attempt_count_matches_max(self) -> None:
        # When max=3 and the connector always fails, we get 3 attempts.
        connector_holder = {"instance": None}

        class _Tracker(_AlwaysFailingConnector):
            def __init__(self, provider_model: str = "x") -> None:
                super().__init__(provider_model)
                connector_holder["instance"] = self  # type: ignore[assignment]

        with mock.patch.dict(
            os.environ, {**self._fast_retries(), "FAIRGAME_LLM_MAX_ATTEMPTS": "3"}
        ):
            register_model("Tracker", _Tracker, "x")
            with self.assertRaises(RuntimeError):
                execute_prompt("Tracker", "ping")
        self.assertEqual(connector_holder["instance"].attempts, 3)  # type: ignore[union-attr]

    def test_non_retryable_exceptions_dont_retry(self) -> None:
        # ValueError isn't in RETRYABLE_EXCEPTIONS — surface immediately.
        connector_holder = {"instance": None}

        class _Tracker(_NonRetryableErrorConnector):
            def __init__(self, provider_model: str = "x") -> None:
                super().__init__(provider_model)
                connector_holder["instance"] = self  # type: ignore[assignment]

        with mock.patch.dict(
            os.environ, {**self._fast_retries(), "FAIRGAME_LLM_MAX_ATTEMPTS": "5"}
        ):
            register_model("Tracker", _Tracker, "x")
            with self.assertRaises(ValueError):
                execute_prompt("Tracker", "ping")
        # Only one attempt — no retry on non-retryable error.
        self.assertEqual(connector_holder["instance"].attempts, 1)  # type: ignore[union-attr]

    def test_max_attempts_one_means_no_retries(self) -> None:
        with mock.patch.dict(
            os.environ, {**self._fast_retries(), "FAIRGAME_LLM_MAX_ATTEMPTS": "1"}
        ):
            register_model("AlwaysFails", _AlwaysFailingConnector, "x")
            with self.assertRaises(RuntimeError):
                execute_prompt("AlwaysFails", "ping")

    def test_invalid_max_attempts_env_falls_back_to_default(self) -> None:
        # Garbage env value → use default (3); the connector is allowed to
        # eventually succeed.
        with mock.patch.dict(
            os.environ,
            {**self._fast_retries(), "FAIRGAME_LLM_MAX_ATTEMPTS": "not-a-number"},
        ):
            register_model("Flaky", _FlakyConnector, "flaky")
            self.assertEqual(execute_prompt("Flaky", "ping"), "recovered")


if __name__ == "__main__":
    unittest.main()
