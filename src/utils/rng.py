"""Centralised RNG helpers for deterministic / replayable runs.

Every place that needs randomness in FAIRGAME (type draws, fake messages,
mixed-strategy sampling, baseline RandomChoice, indefinite-horizon
continuation checks, multi-seed orchestration) goes through a
:class:`random.Random` instance returned by :func:`make_rng`. Pass an
explicit ``seed`` to make a run reproducible; pass ``None`` for nondeterminism.
"""

from __future__ import annotations

import random
from typing import Optional


def make_rng(seed: Optional[int] = None) -> random.Random:
    """Return a private ``random.Random`` instance seeded with ``seed``.

    Using a private instance (instead of the module-level singleton) means
    parallel games and tests don't leak randomness into each other.
    """
    return random.Random(seed)


def derive_seed(parent: random.Random) -> int:
    """Draw a fresh integer seed from ``parent`` for spawning child RNGs."""
    return parent.randint(0, 2**31 - 1)
