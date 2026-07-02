"""Base class for LLM provider connectors.

Each concrete connector implements :meth:`_send_prompt`. The public
:meth:`send_prompt` wraps it with logging and a tenacity-driven retry policy
so transient provider failures do not bubble up to the caller.
"""

from __future__ import annotations

import abc
import getpass
import os
import tempfile
import threading
import time

import httpx
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.llm_connectors import rate_limiter
from src.utils.logger import get_logger
from src.utils.utils import float_env, int_env

logger = get_logger(__name__)


def _default_rate_file() -> str:
    """Per-user default path for the cross-process rate-limiter bucket.

    A single predictable world-writable path (the old
    ``/tmp/fairgame_llm_rate.bucket``) could be pre-created or poisoned by
    another user on a shared host. Namespacing by uid/username avoids the
    fixed-name collision; operators on multi-tenant hosts should still point
    ``FAIRGAME_LLM_RATE_FILE`` at a path inside a private (0700) directory.
    """
    try:
        owner: object = os.getuid()  # type: ignore[attr-defined]
    except AttributeError:  # pragma: no cover - non-POSIX
        owner = getpass.getuser()
    return os.path.join(tempfile.gettempdir(), f"fairgame_llm_rate_{owner}.bucket")


class AbstractConnector(abc.ABC):
    """Common base for all LLM provider connectors.

    Subclasses must implement :meth:`_send_prompt` and may override
    :attr:`RETRYABLE_EXCEPTIONS` to widen the set of errors that trigger a
    retry (e.g. the provider SDK's rate-limit / 5xx exception types). Retry
    behaviour is configured by env vars:

    * ``FAIRGAME_LLM_MAX_ATTEMPTS`` (default ``3``)
    * ``FAIRGAME_LLM_BACKOFF_MIN`` seconds (default ``1.0``)
    * ``FAIRGAME_LLM_BACKOFF_MAX`` seconds (default ``10.0``)
    """

    # Narrow transient default: only network connection / timeout errors are
    # retried. Retrying every ``Exception`` (the old default) burned the whole
    # backoff budget on non-transient failures (auth, 400s, the connectors'
    # own ``ValueError``), masking real bugs as long hangs. ``ConnectionError``
    # and ``TimeoutError`` are builtins (both subclasses of ``OSError``);
    # provider connectors widen this with their SDK's transient types.
    # ``httpx.TransportError`` (the base of ReadTimeout / ConnectError /
    # NetworkError etc.) is included because both the Mistral and Replicate
    # SDKs are httpx-based and raise it for transient I/O — and, crucially,
    # ``httpx.ReadTimeout`` is NOT a builtin ``TimeoutError`` subclass, so it
    # would otherwise escape retry.
    RETRYABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (
        ConnectionError,
        TimeoutError,
        httpx.TransportError,
    )

    # Shared request timeout (seconds). Bounds each provider call so a hung
    # connection can't freeze a worker; subclasses pass it to their SDK
    # client (in ms where the SDK wants ms). Override via FAIRGAME_LLM_TIMEOUT
    # — read per-instance in ``__init__`` (NOT at import time) so a value set
    # by ``load_dotenv()`` after this module is imported still takes effect.
    REQUEST_TIMEOUT_SECONDS: float = 60.0

    # Process-wide pacing: minimum seconds between the START of consecutive
    # requests from this process. Connectors are re-instantiated per call, so
    # the timestamp/lock must live on the class to persist across calls.
    # Set via FAIRGAME_LLM_MIN_INTERVAL to respect provider rate limits
    # (e.g. Mistral's 6 req/s -> run N workers at interval N/6).
    _throttle_lock = threading.Lock()
    _last_call_ts = 0.0

    def __init__(self) -> None:
        self.REQUEST_TIMEOUT_SECONDS = float_env("FAIRGAME_LLM_TIMEOUT", 60.0)
        self._max_attempts = max(1, int_env("FAIRGAME_LLM_MAX_ATTEMPTS", 3))
        self._backoff_min = float_env("FAIRGAME_LLM_BACKOFF_MIN", 1.0)
        self._backoff_max = float_env("FAIRGAME_LLM_BACKOFF_MAX", 10.0)
        self._min_interval = float_env("FAIRGAME_LLM_MIN_INTERVAL", 0.0)
        # Cross-process token bucket (shared file). Set FAIRGAME_LLM_RATE_LIMIT
        # to the aggregate requests/sec budget to coordinate many workers.
        self._rate_limit = float_env("FAIRGAME_LLM_RATE_LIMIT", 0.0)
        self._rate_capacity = float_env("FAIRGAME_LLM_RATE_CAPACITY", max(1.0, self._rate_limit))
        self._rate_file = os.getenv("FAIRGAME_LLM_RATE_FILE") or _default_rate_file()

    def _throttle(self) -> None:
        """Block until at least ``_min_interval`` has passed since the last call."""
        if self._min_interval <= 0:
            return
        # Reserve this call's start slot under the lock, then release it BEFORE
        # sleeping. Holding the lock across ``time.sleep`` would fully serialize
        # workers and stack their waits. Advancing ``_last_call_ts`` to the
        # reserved slot lets concurrent callers each get a distinct,
        # non-overlapping start time without anyone blocking on the lock.
        with AbstractConnector._throttle_lock:
            now = time.monotonic()
            scheduled = max(now, AbstractConnector._last_call_ts + self._min_interval)
            AbstractConnector._last_call_ts = scheduled
        wait = scheduled - now
        if wait > 0:
            time.sleep(wait)

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
                if self._rate_limit > 0:
                    rate_limiter.acquire(self._rate_limit, self._rate_capacity, self._rate_file)
                self._throttle()
                return self._send_prompt(prompt)
        # Unreachable: tenacity either returns from the with-block or raises.
        raise RuntimeError("Retry loop exited unexpectedly")  # pragma: no cover
