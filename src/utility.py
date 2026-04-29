"""Utility-function transforms applied to raw payoffs after a round.

A :class:`UtilityTransform` maps the vector of agents' realised payoffs in
one round into a (possibly different) vector of utilities. This lets
researchers study risk aversion, inequity aversion, etc. without changing
the underlying payoff matrix.

Available transforms:

* :class:`IdentityTransform` — no change (default).
* :class:`CRRATransform` — constant relative risk aversion: ``u(x) =
  (x^(1-γ) - 1) / (1 - γ)`` for ``γ ≠ 1``; ``u(x) = ln(x)`` for ``γ = 1``.
  Negative or zero raw payoffs are shifted by ``offset`` so the log /
  power is well-defined.
* :class:`FehrSchmidtTransform` — inequity aversion: each agent's utility
  is its own payoff minus α times the average of payoffs above its own
  and minus β times the average of payoffs below its own.

Build one from a config dict via :func:`build_utility_transform`.
"""

from __future__ import annotations

import abc
import math
from typing import Any, Dict, List, Sequence

from src.utils.logger import get_logger

logger = get_logger(__name__)


class UtilityTransform(abc.ABC):
    """Per-round utility mapping from raw payoffs to agent utilities."""

    @abc.abstractmethod
    def transform(self, payoffs: Sequence[float]) -> List[float]:
        """Return the utility vector for the given round."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Human-readable identifier; used in result metadata."""


class IdentityTransform(UtilityTransform):
    """Pass payoffs through unchanged."""

    name = "identity"

    def transform(self, payoffs: Sequence[float]) -> List[float]:
        return list(payoffs)


class CRRATransform(UtilityTransform):
    """Constant relative risk aversion (per-agent, then summed elsewhere).

    Args:
        gamma: Relative risk-aversion coefficient. ``0`` is risk-neutral;
            higher is more risk averse. ``1`` is the log case.
        offset: Added to each raw payoff before applying the transform so
            zero or negative payoffs don't blow up the log/power.
    """

    name = "crra"

    def __init__(self, gamma: float, offset: float = 1.0) -> None:
        if gamma < 0:
            raise ValueError("CRRA gamma must be non-negative.")
        self.gamma = float(gamma)
        self.offset = float(offset)

    def _u(self, x: float) -> float:
        z = x + self.offset
        if z <= 0:
            raise ValueError(
                f"CRRA requires positive shifted payoff; got {z}. "
                "Increase 'offset' to lift all payoffs above zero."
            )
        if math.isclose(self.gamma, 1.0):
            return math.log(z)
        return (z ** (1 - self.gamma) - 1) / (1 - self.gamma)

    def transform(self, payoffs: Sequence[float]) -> List[float]:
        return [self._u(float(p)) for p in payoffs]


class FehrSchmidtTransform(UtilityTransform):
    """Fehr-Schmidt (1999) inequity-aversion utility.

    For agent ``i`` with payoff ``x_i`` and others ``x_j``::

        u_i = x_i - α/(n-1) Σ_j max(x_j - x_i, 0) - β/(n-1) Σ_j max(x_i - x_j, 0)

    ``α`` is the *envy* (disadvantageous inequity) weight; ``β`` is the
    *guilt* (advantageous inequity) weight. Conventional empirical estimates
    have ``β ≤ α`` and both in ``[0, 1]``.
    """

    name = "fehr_schmidt"

    def __init__(self, alpha: float, beta: float) -> None:
        if alpha < 0 or beta < 0:
            raise ValueError("Fehr-Schmidt alpha/beta must be non-negative.")
        self.alpha = float(alpha)
        self.beta = float(beta)

    def transform(self, payoffs: Sequence[float]) -> List[float]:
        n = len(payoffs)
        if n == 0:
            return []
        if n == 1:
            return [float(payoffs[0])]
        utilities: List[float] = []
        for i, xi in enumerate(payoffs):
            envy = sum(max(xj - xi, 0.0) for j, xj in enumerate(payoffs) if j != i)
            guilt = sum(max(xi - xj, 0.0) for j, xj in enumerate(payoffs) if j != i)
            ui = float(xi) - self.alpha * envy / (n - 1) - self.beta * guilt / (n - 1)
            utilities.append(ui)
        return utilities


def _camel_to_snake(name: str) -> str:
    out = []
    for i, c in enumerate(name):
        if c.isupper() and i > 0 and not name[i - 1].isupper():
            out.append("_")
        out.append(c.lower())
    return "".join(out)


_TRANSFORM_REGISTRY = {
    "identity": IdentityTransform,
    "crra": CRRATransform,
    "fehr_schmidt": FehrSchmidtTransform,
    "fehrSchmidt": FehrSchmidtTransform,
    "fehr-schmidt": FehrSchmidtTransform,
}


def build_utility_transform(config: Dict[str, Any] | None) -> UtilityTransform:
    """Construct a :class:`UtilityTransform` from a config dict.

    Examples::

        build_utility_transform(None)                                   # identity
        build_utility_transform({"type": "CRRA", "gamma": 0.5})         # risk-averse
        build_utility_transform({"type": "FehrSchmidt", "alpha": 0.4,  # inequity-averse
                                 "beta": 0.6})
    """
    if not config:
        return IdentityTransform()
    raw_type = config.get("type", "identity")
    cls = (
        _TRANSFORM_REGISTRY.get(raw_type)
        or _TRANSFORM_REGISTRY.get(str(raw_type).lower())
        or _TRANSFORM_REGISTRY.get(_camel_to_snake(str(raw_type)))
    )
    if cls is None:
        raise ValueError(
            f"Unknown utility transform type {raw_type!r}. "
            f"Known: {sorted(set(_TRANSFORM_REGISTRY))}"
        )
    kwargs = {k: v for k, v in config.items() if k != "type"}
    return cls(**kwargs)
