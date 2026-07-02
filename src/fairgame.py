"""Top-level game engine.

A :class:`FairGame` orchestrates a sequence of rounds, applies the configured
payoff matrix, finalises each round's scores through a single documented
pipeline (utility transform → discount → trust look-costs), and stops when
either the round limit is reached or one of the listed stop combinations is
observed.
"""

from __future__ import annotations

from typing import Any

from src.game_config import CONFIG_FIELD_NAMES, GameConfig
from src.game_history import GameHistory
from src.game_round import GameRound
from src.payoff_matrix import PayoffMatrix
from src.utils.logger import get_logger
from src.utils.rng import make_rng

logger = get_logger(__name__)

# Config fields readable via attribute forwarding on the game. ``rng`` is
# excluded: the game owns a *runtime* RNG (derived from the config's rng/seed)
# and must be able to assign it in __init__.
_FORWARDED_CONFIG_FIELDS = CONFIG_FIELD_NAMES - {"rng"}


class FairGame:
    """Coordinates rounds, payoff scoring, and stop conditions for one game.

    Holds an immutable :class:`GameConfig` (the single declaration site for
    every per-game parameter — including the fake-communication / trust /
    interaction collaborators) plus the runtime state a game accumulates as
    it plays. Config parameters are exposed read-only via ``__getattr__``
    forwarding, so the engine keeps reading them as ``game.n_rounds`` etc.
    while ``GameConfig`` stays the only place they are declared; assigning
    to a config field on the game raises instead of silently shadowing it.
    """

    def __init__(self, config: GameConfig, agents: dict[str, Any]) -> None:
        self.config = config
        self.agents = dict(agents)

        # ---- Runtime state (mutated as the game plays) ------------------
        self.current_round = 1
        self.history = GameHistory()
        self.choices_made: list[list[str]] = []
        self.payoff_matrix = PayoffMatrix(config.payoff_matrix_data, config.language)
        # Phase list, resolved once on first access (see ``phases``); the
        # laziness is now just caching — everything it needs is in config.
        self._phases_cache: list[Any] | None = None
        # RNG: explicit instance > derived-from-seed > nondeterministic.
        self.rng = config.rng if config.rng is not None else make_rng(config.seed)

        self._warn_if_discount_and_continuation_compound()

    @classmethod
    def from_config(cls, config: GameConfig, agents: dict[str, Any]) -> FairGame:
        """Construct from a :class:`GameConfig` plus the agent dict."""
        return cls(config, agents)

    # ---- Read-only forwarding of the immutable config -------------------

    def __getattr__(self, name: str) -> Any:
        # Only reached when ``name`` is not a real instance attribute.
        if name in _FORWARDED_CONFIG_FIELDS:
            return getattr(self.config, name)
        raise AttributeError(f"{type(self).__name__!r} object has no attribute {name!r}")

    def __setattr__(self, name: str, value: Any) -> None:
        if name in _FORWARDED_CONFIG_FIELDS:
            raise AttributeError(
                f"{name!r} is a config parameter and is read-only on the game; "
                f"config is immutable after construction (game.config.{name} "
                f"exists but mutating it mid-game is almost always a bug)."
            )
        super().__setattr__(name, value)

    @property
    def phases(self) -> list[Any]:
        """The ordered phase list for this game, resolved once then frozen.

        Freezing makes the round's control flow an explicit property of the
        game rather than something re-derived from attributes every round.
        """
        if self._phases_cache is None:
            from src.phases import phases_for_game  # local: avoid import cycle

            self._phases_cache = phases_for_game(self)
        return self._phases_cache

    @property
    def description(self) -> dict[str, Any]:
        """Serialisable summary: config fields + runtime-only additions.

        The config-derived keys come from :meth:`GameConfig.to_description`;
        this adds only what the config can't know — the agent roster and the
        constructed payoff matrix.
        """
        desc = self.config.to_description()
        desc["agents"] = {name: agent.get_info() for name, agent in self.agents.items()}
        desc["payoff_matrix"] = self.payoff_matrix.matrix_data
        return desc

    def _warn_if_discount_and_continuation_compound(self) -> None:
        cp = self.continuation_probability
        df = self.discount_factor
        if cp is not None and cp < 1.0 and df < 1.0:
            logger.warning(
                "Both discount_factor (%.3f) and continuation_probability (%.3f) "
                "are set with values below 1.0. Their effects compound — the "
                "effective per-round discount becomes %.3f. Standard practice "
                "uses one or the other, not both.",
                df,
                cp,
                df * cp,
            )

    def run_round(self) -> None:
        round_runner = GameRound(self)
        round_strategies = round_runner.run()
        self.choices_made.append(round_strategies)
        self.payoff_matrix.attribute_scores(list(self.agents.values()), round_strategies)
        self._finalise_round_scores(round_runner)
        round_runner.record_round_history()

    def _finalise_round_scores(self, round_runner=None) -> None:
        """Single owner of the post-payoff score pipeline for this round.

        Stages, in this order, computed from the raw matrix payoff and then
        written back to each agent's ``scores[-1]`` exactly once:

        1. **Utility transform** — skipped when the preference is prompt-side
           only (``risk_mode == "prompt"`` + CRRA): a preference described to
           the agent shapes its *choices*; also transforming the score would
           count it twice (treatment + measurement). ``"score"`` (legacy
           default) and ``"both"`` still apply it. Fehr-Schmidt has no
           prompt-side support yet, so it always applies regardless.
        2. **Discount** — ``discount_factor ** (round - 1)``, likewise
           skipped when ``discount_mode == "prompt"``.
        3. **Trust look-costs** — agents who paid to LOOK this round have the
           cost deducted last, so the recorded score is the net payoff the
           agent actually keeps.

        Keeping all three in one method makes the ordering a stated contract
        instead of an accident of call sequence.
        """
        agents = list(self.agents.values())
        raw = [float(agent.scores[-1]) for agent in agents]

        # Stage 1: utility transform.
        transform_is_prompt_only = (
            self.risk_mode == "prompt"
            and getattr(self.utility_transform, "name", "identity") == "crra"
        )
        # A prompt-only CRRA transform leaves the numeric scores untouched (the
        # curvature is conveyed in the prompt, not applied to the payoffs).
        utilities = list(raw) if transform_is_prompt_only else self.utility_transform.transform(raw)
        if len(utilities) != len(raw):
            raise RuntimeError("Utility transform must return the same number of values as agents.")

        # Stage 2: discount.
        if self.discount_mode == "prompt":
            discount = 1.0
        else:
            discount = self.discount_factor ** (self.current_round - 1)

        # Stage 3: trust look-costs.
        from src.trust import LOOK  # local: avoid import cycle

        trust_cfg = self.trust_config
        trust_on = bool(trust_cfg and getattr(trust_cfg, "enabled", False))
        look_cost = float(getattr(trust_cfg, "look_cost", 0.0) or 0.0) if trust_on else 0.0
        decisions = getattr(round_runner, "trust_decisions", {}) if round_runner else {}

        for agent, u in zip(agents, utilities, strict=True):
            value = u * discount
            if trust_on and look_cost and decisions.get(agent.name) == LOOK:
                value -= look_cost
            agent.scores[-1] = value

    def stop_condition_is_met(self) -> bool:
        if not self.choices_made:
            return False
        try:
            combination = self.payoff_matrix.get_combination_key(self.choices_made[-1])
        except ValueError:
            return False
        return combination in self.stop_conditions

    def _continuation_check_passes(self) -> bool:
        """For indefinite-horizon games, decide whether to play another round."""
        if self.continuation_probability is None or self.current_round == 1:
            return True
        return self.rng.random() < self.continuation_probability

    def run(self) -> GameHistory:
        while (
            self.current_round <= self.n_rounds
            and not self.stop_condition_is_met()
            and self._continuation_check_passes()
        ):
            self.run_round()
            self.current_round += 1
        return self.history
