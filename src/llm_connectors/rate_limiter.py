"""Cross-process token-bucket rate limiter backed by a lock file.

All worker processes that point at the same ``path`` share one token bucket,
so the *aggregate* request rate across processes stays under a provider cap
(e.g. Mistral's 6 req/s). A per-process throttle can't do this — only a shared
bucket coordinates independent processes.

Usage (via AbstractConnector, env-gated):
    acquire(rate=5.0, capacity=5.0, path="/tmp/fairgame_llm_rate.bucket")
blocks until a token is available, then consumes one.
"""

from __future__ import annotations

import fcntl
import os
import tempfile
import time


def _read_state(path: str, capacity: float, now: float) -> tuple[float, float]:
    try:
        with open(path) as f:
            tokens_s, ts_s = f.read().split()
            return float(tokens_s), float(ts_s)
    except (FileNotFoundError, ValueError):
        return capacity, now  # first use: start with a full bucket


def _write_state(path: str, tokens: float, ts: float) -> None:
    # Atomic: a torn in-place write (process killed mid-write) would leave an
    # empty/garbled file, which ``_read_state`` treats as "first use → full
    # bucket" — silently resetting the shared cap exactly when it matters.
    # Write to a temp file in the same dir, then ``os.replace``.
    directory = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".rate_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(f"{tokens} {ts}")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def acquire(rate: float, capacity: float, path: str) -> None:
    """Block until a token is available across all processes, then consume one.

    Args:
        rate: tokens refilled per second (set below the provider cap).
        capacity: bucket size / max burst.
        path: shared state file; one bucket per distinct path.
    """
    if rate <= 0:
        return
    lock_path = path + ".lock"
    while True:
        with open(lock_path, "w") as lf:
            fcntl.flock(lf, fcntl.LOCK_EX)  # serialize all processes here
            try:
                now = time.time()
                tokens, last = _read_state(path, capacity, now)
                tokens = min(capacity, tokens + (now - last) * rate)
                if tokens >= 1.0:
                    _write_state(path, tokens - 1.0, now)
                    return
                # Not enough yet: persist the refill and compute the wait.
                _write_state(path, tokens, now)
                wait = (1.0 - tokens) / rate
            finally:
                fcntl.flock(lf, fcntl.LOCK_UN)
        time.sleep(min(wait, 0.5))  # sleep outside the lock, then re-check
