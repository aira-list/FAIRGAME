"""Typed bundle of all per-game parameters.

Originally :class:`FairGame.__init__` accepted 18 keyword arguments. That
surface is hostile to readers: easy to mis-order, hard to validate
holistically, and impossible to pass around as a single object. This
dataclass centralises construction, runs cross-field validation in
``__post_init__``, and gives callers a single typed object to thread
through the engine.

Backwards compatibility: :class:`FairGame.__init__` still accepts the
individual kwargs. New code should prefer :meth:`FairGame.from_config`.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from src.utility import IdentityTransform, UtilityTransform


@dataclass
class GameConfig:
    """All per-game parameters in one validated object."""

    # ---- Required core ---------------------------------------------------
    name: str
    language: str
    n_rounds: int
    n_rounds_known: bool
    payoff_matrix_data: Dict[str, Any]
    prompt_template: str
    stop_conditions: List[str]
    agents_communicate: bool

    # ---- Theory of Mind --------------------------------------------------
    elicit_beliefs: bool = False
    tom_order: int = 1
    types_config: Optional[Dict[str, Any]] = None
    types_common_knowledge: bool = False

    # ---- Game-theoretic extensions --------------------------------------
    utility_transform: UtilityTransform = field(default_factory=IdentityTransform)
    discount_factor: float = 1.0
    continuation_probability: Optional[float] = None
    equilibria: Sequence[str] = field(default_factory=list)
    pareto_optimal_sum: Optional[float] = None
    mixed_strategies: bool = False
    reputation_window: Optional[int] = None
    reputation_applies: bool = True

    # ---- RNG -------------------------------------------------------------
    rng: Optional[random.Random] = None
    seed: Optional[int] = None

    def __post_init__(self) -> None:
        if not (0.0 < self.discount_factor <= 1.0):
            raise ValueError(
                f"discount_factor must lie in (0, 1]; got {self.discount_factor}."
            )
        if self.continuation_probability is not None and not (
            0.0 < self.continuation_probability <= 1.0
        ):
            raise ValueError(
                "continuation_probability must lie in (0, 1] when set; "
                f"got {self.continuation_probability}."
            )
