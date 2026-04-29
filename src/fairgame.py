"""Top-level game engine.

A :class:`FairGame` orchestrates a sequence of rounds, applies the configured
payoff matrix, optionally transforms payoffs via a utility function, applies
a discount factor, checks an indefinite-horizon continuation, and stops when
either the round limit is reached or one of the listed stop combinations is
observed.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Mapping, Optional, Sequence

from src.game_history import GameHistory
from src.game_round import GameRound
from src.payoff_matrix import PayoffMatrix
from src.utility import IdentityTransform, UtilityTransform
from src.utils.logger import get_logger
from src.utils.rng import make_rng

logger = get_logger(__name__)


class FairGame:
    """Coordinates rounds, payoff scoring, and stop conditions for one game."""

    def __init__(
        self,
        name: str,
        language: str,
        agents: Mapping[str, Any],
        n_rounds: int,
        n_rounds_known: bool,
        payoff_matrix_data: Dict,
        prompt_template: str,
        stop_conditions: List[str],
        agents_communicate: bool,
        *,
        elicit_beliefs: bool = False,
        tom_order: int = 1,
        types_config: Optional[Dict[str, Any]] = None,
        types_common_knowledge: bool = False,
        utility_transform: Optional[UtilityTransform] = None,
        discount_factor: float = 1.0,
        continuation_probability: Optional[float] = None,
        equilibria: Optional[Sequence[str]] = None,
        pareto_optimal_sum: Optional[float] = None,
        mixed_strategies: bool = False,
        rng: Optional[random.Random] = None,
        seed: Optional[int] = None,
    ) -> None:
        self.name = name
        self.language = language
        self.agents = dict(agents)
        self.n_rounds = int(n_rounds)
        self.n_rounds_known = bool(n_rounds_known)
        self.prompt_template = prompt_template
        self.stop_conditions = stop_conditions
        self.agents_communicate = bool(agents_communicate)
        self.current_round = 1
        self.history = GameHistory()
        self.choices_made: List[List[str]] = []
        self.payoff_matrix = PayoffMatrix(payoff_matrix_data, language)
        self.fake_communication_config: Optional[Any] = None

        # Theory-of-Mind configuration.
        self.elicit_beliefs = bool(elicit_beliefs)
        self.tom_order = int(tom_order)
        self.types_config = types_config
        self.types_common_knowledge = bool(types_common_knowledge)

        # Game-theoretic extensions.
        self.utility_transform: UtilityTransform = utility_transform or IdentityTransform()
        if not (0.0 < discount_factor <= 1.0):
            raise ValueError("discount_factor must lie in (0, 1].")
        self.discount_factor = float(discount_factor)
        if continuation_probability is not None and not (0.0 < continuation_probability <= 1.0):
            raise ValueError("continuation_probability must lie in (0, 1] when set.")
        self.continuation_probability = (
            float(continuation_probability) if continuation_probability is not None else None
        )
        self.equilibria: List[str] = list(equilibria or [])
        self.pareto_optimal_sum = pareto_optimal_sum
        self.mixed_strategies = bool(mixed_strategies)

        # RNG: explicit instance > derived-from-seed > nondeterministic.
        self.seed = seed
        self.rng = rng if rng is not None else make_rng(seed)

    @property
    def description(self) -> Dict[str, Any]:
        """Serialisable summary of the game configuration."""
        desc: Dict[str, Any] = {
            "name": self.name,
            "language": self.language,
            "agents": {name: agent.get_info() for name, agent in self.agents.items()},
            "n_rounds": self.n_rounds,
            "number_of_rounds_is_known": self.n_rounds_known,
            "payoff_matrix": self.payoff_matrix.matrix_data,
            "agents_communicate": self.agents_communicate,
        }

        if self.fake_communication_config is not None:
            cfg = self.fake_communication_config
            desc["fake_communication"] = cfg.enabled
            desc["fake_message_count"] = getattr(cfg, "message_count", None)
            desc["fake_message_base"] = getattr(cfg, "base", None)

        desc["elicit_beliefs"] = self.elicit_beliefs
        desc["tom_order"] = self.tom_order
        if self.types_config is not None:
            desc["types"] = self.types_config
            desc["types_common_knowledge"] = self.types_common_knowledge

        desc["utility_transform"] = self.utility_transform.name
        desc["discount_factor"] = self.discount_factor
        if self.continuation_probability is not None:
            desc["continuation_probability"] = self.continuation_probability
        if self.equilibria:
            desc["equilibria"] = list(self.equilibria)
        if self.pareto_optimal_sum is not None:
            desc["pareto_optimal_sum"] = self.pareto_optimal_sum
        desc["mixed_strategies"] = self.mixed_strategies
        if self.seed is not None:
            desc["seed"] = self.seed

        return desc

    def log_game_info(self) -> None:
        logger.info(
            "FAIRGAME config: name=%s language=%s rounds=%d known=%s communicate=%s δ=%s",
            self.name,
            self.language,
            self.n_rounds,
            self.n_rounds_known,
            self.agents_communicate,
            self.discount_factor,
        )
        for name, agent in self.agents.items():
            info = agent.get_info()
            logger.info(
                "  agent=%s personality=%s llm=%s opp_prob=%s",
                name,
                info.get("personality"),
                info.get("llm_service"),
                info.get("opponent_personality_probability"),
            )

    print_game_info = log_game_info

    def run_round(self) -> None:
        round_runner = GameRound(self)
        round_strategies = round_runner.run()
        self.choices_made.append(round_strategies)
        self.payoff_matrix.attribute_scores(list(self.agents.values()), round_strategies)
        self._apply_score_modifiers()
        round_runner._update_round_history()

    def _apply_score_modifiers(self) -> None:
        """Apply utility transform + discount to the most recent round's payoffs."""
        agents = list(self.agents.values())
        raw = [float(agent.scores[-1]) for agent in agents]
        utilities = self.utility_transform.transform(raw)
        if len(utilities) != len(raw):
            raise RuntimeError(
                "Utility transform must return the same number of values as agents."
            )
        discount = self.discount_factor ** (self.current_round - 1)
        for agent, u in zip(agents, utilities):
            agent.scores[-1] = u * discount

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
