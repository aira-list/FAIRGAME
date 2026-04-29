"""Base class for LLM provider connectors.

Each concrete connector implements :meth:`_send_prompt`. The public
:meth:`send_prompt` wraps it with logging and a tenacity-driven retry policy
so transient provider failures do not bubble up to the caller.
"""

from __future__ import annotations

import abc
import os
from typing import Any

from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.utils.logger import get_logger

logger = get_logger(__name__)


def _int_env(name: str, default: int) -> int:
    """Read an integer env var, falling back to ``default`` on parse errors."""
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid value for %s=%r; using default %d.", name, raw, default)
        return default


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning("Invalid value for %s=%r; using default %s.", name, raw, default)
        return default


class AbstractConnector(abc.ABC):
    """Common base for all LLM provider connectors.

    Subclasses must implement :meth:`_send_prompt` and may override
    :attr:`RETRYABLE_EXCEPTIONS` to widen the set of errors that trigger a
    retry. Retry behaviour is configured by env vars:

    * ``FAIRGAME_LLM_MAX_ATTEMPTS`` (default ``3``)
    * ``FAIRGAME_LLM_BACKOFF_MIN`` seconds (default ``1.0``)
    * ``FAIRGAME_LLM_BACKOFF_MAX`` seconds (default ``10.0``)
    """

    RETRYABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (Exception,)

    def __init__(self) -> None:
        self._max_attempts = max(1, _int_env("FAIRGAME_LLM_MAX_ATTEMPTS", 3))
        self._backoff_min = _float_env("FAIRGAME_LLM_BACKOFF_MIN", 1.0)
        self._backoff_max = _float_env("FAIRGAME_LLM_BACKOFF_MAX", 10.0)

    @abc.abstractmethod
    def _send_prompt(self, prompt: str) -> str:
        """Issue a single request to the provider and return the response text."""

    def send_prompt(self, prompt: str) -> str:
        """Send a prompt with retries on transient errors."""
        retrying = Retrying(
            stop=stop_after_attempt(self._max_attempts),
            wait=wait_exponential(min=self._backoff_min, max=self._backoff_max),
            retry=retry_if_exception_type(self.RETRYABLE_EXCEPTIONS),
            reraise=True,
        )
        for attempt in retrying:
            with attempt:
                logger.debug(
                    "%s attempt %d/%d",
                    type(self).__name__,
                    attempt.retry_state.attempt_number,
                    self._max_attempts,
                )
                return self._send_prompt(prompt)
        # Unreachable: tenacity either returns from the with-block or raises.
        raise RuntimeError("Retry loop exited unexpectedly")  # pragma: no cover

    # Backwards-compatibility shim for tests/code that mock ``send_prompt``.
    def __call__(self, prompt: str) -> Any:  # pragma: no cover - convenience
        return self.send_prompt(prompt)
