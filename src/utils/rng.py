"""Centralised RNG helpers for deterministic / replayable runs.

Every place that needs randomness in FAIRGAME (type draws, fake messages,
mixed-strategy sampling, baseline RandomChoice, indefinite-horizon
continuation checks, multi-seed orchestration) goes through a
:class:`random.Random` instance returned by :func:`make_rng`. Pass an
explicit ``seed`` to make a run reproducible; pass ``None`` for nondeterminism.
"""

from __future__ import annotations

import hashlib
import random


def make_rng(seed: int | None = None) -> random.Random:
    """Return a private ``random.Random`` instance seeded with ``seed``.

    Using a private instance (instead of the module-level singleton) means
    parallel games and tests don't leak randomness into each other.
    """
    return random.Random(seed)


def combine_seed(*parts: int) -> int:
    """Deterministically fold integers into a single 32-bit seed.

    Used to derive a per-cell seed from independent axes (e.g. a multi-seed
    base and a tournament pair index). Unlike plain addition
    (``base + pair_idx``), distinct axis combinations cannot collide:
    ``(10, 1)`` and ``(11, 0)`` map to different seeds. Unlike the builtin
    ``hash()`` it is stable across processes (no PYTHONHASHSEED salt).
    """
    payload = ":".join(str(int(p)) for p in parts).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "big")
