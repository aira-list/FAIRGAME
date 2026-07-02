"""Canonical (non-LLM) strategies used as baselines and tournament entries.

A :class:`BaselineStrategy` decides an action from game state alone. The
contract is identical to (a much-simplified version of) what an LLM agent
would produce: given the current game and round number it returns a
canonical strategy *key* (e.g. ``"strategy1"``).

Strategies in the library:

* :class:`AlwaysCooperate` — always plays the cooperate strategy.
* :class:`AlwaysDefect` — always plays the defect strategy.
* :class:`RandomChoice` — uniform random over all strategies.
* :class:`TitForTat` — round 1 cooperate; thereafter mirrors the opponent's
  most recent action. With multiple opponents the rule is "cooperate iff
  *all* opponents cooperated last round".
* :class:`GrimTrigger` — cooperate until any opponent has ever defected,
  then defect forever.
* :class:`RandomMixed` — sample from a fixed user-supplied distribution.

The two distinguished strategies — *cooperate* and *defect* — are read from
the game's ``baseline_semantics`` mapping. By convention the first
strategy key (``strategy1``) is "cooperate" and the last is "defect", but
both can be overridden via the config block::

    "baselineSemantics": {"cooperate": "strategy1", "defect": "strategy2"}
"""

from __future__ import annotations

import abc
import random
from collections.abc import Mapping
from typing import Any

from src.payoff_matrix import label_to_key_map


def cooperate_key(game) -> str:
    """Return the strategy key that counts as 'cooperate' for this game."""
    semantics = getattr(game, "baseline_semantics", None) or {}
    if "cooperate" in semantics:
        return semantics["cooperate"]
    return next(iter(game.payoff_matrix.strategies))


def defect_key(game) -> str:
    semantics = getattr(game, "baseline_semantics", None) or {}
    if "defect" in semantics:
        return semantics["defect"]
    keys = list(game.payoff_matrix.strategies)
    return keys[-1]


def _completed_strategies(opponent, round_number: int) -> list:
    """The opponent's strategy labels from *completed* rounds only.

    The choose phase runs agents sequentially and appends each pick to
    ``agent.strategies`` immediately, so during round N an earlier-moving
    opponent already has its round-N entry. A baseline may only react to
    rounds before the current one — otherwise it sees the co-player's
    same-round move (lookahead cheating).
    """
    return list(opponent.strategies[: max(0, round_number - 1)])


def _opponent_last_strategy_key(game, opponent, round_number: int) -> str | None:
    """Look up the opponent's most recent completed-round strategy *key*."""
    history = _completed_strategies(opponent, round_number)
    if not history:
        return None
    label_to_key = label_to_key_map(game.payoff_matrix.strategies)
    return label_to_key.get(history[-1])


class BaselineStrategy(abc.ABC):
    """Decision rule that consumes game state and returns a strategy key."""

    name: str = "baseline"

    @abc.abstractmethod
    def choose(self, agent, game, round_number: int) -> str:
        """Return a canonical strategy key (not display label)."""

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<{self.name}>"


class AlwaysCooperate(BaselineStrategy):
    name = "always_cooperate"

    def choose(self, agent, game, round_number: int) -> str:
        return cooperate_key(game)


class AlwaysDefect(BaselineStrategy):
    name = "always_defect"

    def choose(self, agent, game, round_number: int) -> str:
        return defect_key(game)


class RandomChoice(BaselineStrategy):
    """Uniform random over all available strategies."""

    name = "random"

    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng

    def choose(self, agent, game, round_number: int) -> str:
        rng = self.rng or game.rng
        return rng.choice(list(game.payoff_matrix.strategies))


class TitForTat(BaselineStrategy):
    """Cooperate first, then mirror the opponent's most recent action.

    With more than one opponent, cooperates iff *all* opponents cooperated
    last round. Defects on the first observed defection from any opponent.
    """

    name = "tit_for_tat"

    def choose(self, agent, game, round_number: int) -> str:
        if round_number == 1:
            return cooperate_key(game)
        coop = cooperate_key(game)
        defect = defect_key(game)
        for opp in game.agents.values():
            if opp is agent:
                continue
            last = _opponent_last_strategy_key(game, opp, round_number)
            if last is not None and last != coop:
                return defect
        return coop


class GrimTrigger(BaselineStrategy):
    """Cooperate until any opponent has ever defected, then defect forever."""

    name = "grim_trigger"

    def choose(self, agent, game, round_number: int) -> str:
        coop = cooperate_key(game)
        defect = defect_key(game)
        label_to_key = label_to_key_map(game.payoff_matrix.strategies)
        for opp in game.agents.values():
            if opp is agent:
                continue
            for label in _completed_strategies(opp, round_number):
                if label_to_key.get(label) == defect:
                    return defect
        return coop


class RandomMixed(BaselineStrategy):
    """Sample from a fixed user-supplied distribution over strategy keys."""

    name = "random_mixed"

    def __init__(self, distribution: Mapping[str, float], rng: random.Random | None = None) -> None:
        if not distribution:
            raise ValueError("RandomMixed distribution must be non-empty.")
        if any(p < 0 for p in distribution.values()):
            raise ValueError("RandomMixed probabilities must be non-negative.")
        total = sum(distribution.values())
        if total <= 0:
            raise ValueError("RandomMixed probabilities must sum to a positive value.")
        self.distribution: dict[str, float] = {k: v / total for k, v in distribution.items()}
        self.rng = rng

    def choose(self, agent, game, round_number: int) -> str:
        rng = self.rng or game.rng
        keys = list(self.distribution.keys())
        weights = list(self.distribution.values())
        return rng.choices(keys, weights=weights, k=1)[0]


# Registry --------------------------------------------------------------

_REGISTRY: dict[str, type[BaselineStrategy]] = {
    "AlwaysCooperate": AlwaysCooperate,
    "AlwaysDefect": AlwaysDefect,
    "Random": RandomChoice,
    "TitForTat": TitForTat,
    "GrimTrigger": GrimTrigger,
    "RandomMixed": RandomMixed,
}


def available_baselines() -> list[str]:
    """Sorted canonical baseline strategy names (the public registry view)."""
    return sorted(_REGISTRY)


BASELINE_PREFIX = "Baseline:"


def is_baseline_id(model_id: str) -> bool:
    """Recognise model identifiers that the factory should resolve to a baseline.

    The prefix match is case-insensitive: the GUI emits the lowercase
    ``baseline:`` form (see ``web/js/app.js``) while configs written by hand
    and the docs use ``Baseline:``. Both must resolve to a baseline.
    """
    return isinstance(model_id, str) and model_id.lower().startswith(BASELINE_PREFIX.lower())


def parse_baseline_id(model_id: str) -> tuple[str, dict[str, Any]]:
    """Return ``(strategy_name, kwargs)`` from a ``Baseline:Name(args)`` id.

    Supports the bare form ``Baseline:TitForTat`` and the parametric form
    ``Baseline:RandomMixed(strategy1=0.7,strategy2=0.3)``. The prefix is
    matched case-insensitively (``baseline:`` from the GUI also works).
    """
    # Split on the first colon so the prefix's case/exact spelling doesn't
    # matter (previously this sliced a fixed length and only worked because
    # "Baseline:" and "baseline:" happen to be the same length).
    body = model_id.split(":", 1)[1] if ":" in model_id else model_id
    if "(" not in body:
        return body, {}
    name, _, rest = body.partition("(")
    rest = rest.rstrip(")")
    kwargs: dict[str, Any] = {}
    for raw in rest.split(","):
        raw = raw.strip()
        if not raw:
            continue
        if "=" not in raw:
            raise ValueError(f"Invalid baseline argument {raw!r} in {model_id!r}.")
        k, v = raw.split("=", 1)
        kwargs[k.strip()] = _coerce(v.strip())
    return name, kwargs


def _coerce(value: str) -> Any:
    try:
        return float(value) if "." in value else int(value)
    except ValueError:
        return value


def make_baseline(model_id: str) -> BaselineStrategy:
    """Instantiate a baseline strategy from its model identifier."""
    name, kwargs = parse_baseline_id(model_id)
    cls = _REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"Unknown baseline strategy {name!r}. Known: {sorted(_REGISTRY)}")
    if cls is RandomMixed:
        # All kwargs are interpreted as the distribution.
        return RandomMixed(distribution=kwargs)
    return cls()
