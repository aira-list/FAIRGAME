"""Single-round execution: communication phase + belief elicitation + strategy selection."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_fixed,
)

from src.belief_parser import BeliefParseError, parse_belief
from src.fake_message_generator import FakeMessageGenerator
from src.prompt_creator import PromptCreator
from src.utils.logger import get_logger

# parse_belief is imported above; alias kept for clarity in mixed-strategy code.

logger = get_logger(__name__)


def _strategy_max_attempts() -> int:
    raw = os.getenv("FAIRGAME_STRATEGY_MAX_ATTEMPTS", "10")
    try:
        return max(1, int(raw))
    except ValueError:
        return 10


def _belief_max_attempts() -> int:
    raw = os.getenv("FAIRGAME_BELIEF_MAX_ATTEMPTS", "3")
    try:
        return max(1, int(raw))
    except ValueError:
        return 3


class GameRound:
    """Encapsulates one round of a FAIRGAME match."""

    def __init__(self, game) -> None:
        self.game = game
        self.round_number = game.current_round

        self.fake_generator = None
        fake_cfg = getattr(game, "fake_communication_config", None)
        if fake_cfg and getattr(fake_cfg, "enabled", False):
            self.fake_generator = FakeMessageGenerator(
                count=fake_cfg.message_count,
                base=fake_cfg.base,
                rng=getattr(game, "rng", None),
            )

    def run(self) -> List[str]:
        """Execute one full round and return the strategy keys chosen."""
        if self.game.agents_communicate:
            self._execute_communication_phase()

        if getattr(self.game, "elicit_beliefs", False):
            self._execute_belief_phase()

        choose_phase = "mixedChoose" if self.game.mixed_strategies else "choose"
        round_strategies: List[str] = []
        for agent in self.game.agents.values():
            prompt = self.create_prompt(agent, phase=choose_phase)
            strategy = self._execute_agent_strategy(agent, prompt)
            round_strategies.append(strategy)

        return round_strategies

    # ---- Communication --------------------------------------------------

    def _execute_communication_phase(self) -> None:
        for agent in self.game.agents.values():
            if self.fake_generator:
                message = self.fake_generator.generate(agent, self.round_number)
            else:
                message = self._get_real_message(agent)

            self.game.history.update_round(
                self.round_number,
                agent.name,
                {"message": message},
            )

    def _get_real_message(self, agent) -> str:
        prompt = self.create_prompt(agent, phase="communicate")
        return agent.execute_round(prompt)

    # ---- Belief elicitation --------------------------------------------

    def _execute_belief_phase(self) -> None:
        """Ask each agent to predict its opponents' next strategy.

        Failures are recorded but do not abort the round — research code
        often wants to see *that* an agent failed to articulate a belief.
        """
        for agent in self.game.agents.values():
            prompt = self.create_prompt(agent, phase="believe")
            belief = self._elicit_one_belief(agent, prompt)
            self.game.history.update_round(
                self.round_number,
                agent.name,
                {"belief": belief, "belief_prompt": prompt},
            )

    def _elicit_one_belief(self, agent, prompt: str) -> Optional[Dict[str, float]]:
        retrying = Retrying(
            stop=stop_after_attempt(_belief_max_attempts()),
            wait=wait_fixed(1),
            retry=retry_if_exception_type(BeliefParseError),
            reraise=True,
        )
        try:
            for attempt in retrying:
                with attempt:
                    response = agent.execute_round(prompt)
                    logger.debug("Agent %s belief raw response: %s", agent.name, response)
                    return parse_belief(response, self.game.payoff_matrix.strategies)
        except BeliefParseError as exc:
            logger.warning(
                "Could not parse belief for agent %s after %d attempts: %s",
                agent.name,
                _belief_max_attempts(),
                exc,
            )
            return None
        return None  # pragma: no cover - tenacity always returns or raises

    # ---- Choose ---------------------------------------------------------

    def create_prompt(self, agent, phase: str) -> str:
        opponents = self._get_opponents(agent)
        prompt_creator = PromptCreator(
            self.game.language,
            self.game.prompt_template,
            self.game.n_rounds,
            self.game.n_rounds_known,
            self.game.payoff_matrix,
            tom_order=getattr(self.game, "tom_order", 1),
            reputation_window=getattr(self.game, "reputation_window", None),
            reputation_applies=getattr(self.game, "reputation_applies", True),
        )
        return prompt_creator.fill_template(
            agent,
            opponents,
            self.round_number,
            self.game.history.rounds,
            phase,
            extra_placeholders=self._tom_placeholders(agent, opponents),
        )

    def _tom_placeholders(self, agent, opponents) -> Dict[str, Any]:
        """Build ToM-aware placeholders (own type, opponent type prior, ...)."""
        values: Dict[str, Any] = {}
        own_type = getattr(agent, "agent_type", None)
        if own_type is not None:
            values["ownType"] = own_type

        types_cfg = getattr(self.game, "types_config", None)
        if types_cfg and getattr(self.game, "types_common_knowledge", False):
            labels = list(types_cfg.get("labels", []))
            probs = types_cfg.get("probs") or [1 / len(labels)] * len(labels)
            values["typeDistribution"] = ", ".join(
                f"{lab}={p:.2f}" for lab, p in zip(labels, probs)
            )
        return values

    def _get_opponents(self, agent):
        return [a for a in self.game.agents.values() if a != agent]

    def _execute_agent_strategy(self, agent, prompt: str) -> str:
        # Baseline (non-LLM) agents short-circuit: they decide from game state.
        baseline = getattr(agent, "baseline_strategy", None)
        if baseline is not None:
            strategy_key = baseline.choose(agent, self.game, self.round_number)
            agent.add_strategy(self.game.payoff_matrix.strategies[strategy_key])
            return strategy_key

        if self.game.mixed_strategies:
            return self._execute_mixed_strategy(agent, prompt)

        retrying = Retrying(
            stop=stop_after_attempt(_strategy_max_attempts()),
            wait=wait_fixed(1),
            retry=retry_if_exception_type(ValueError),
            reraise=True,
        )
        for attempt in retrying:
            with attempt:
                response = agent.execute_round(prompt)
                logger.debug("Agent %s raw response: %s", agent.name, response)
                strategy_key = self._match_strategy(response)
                if strategy_key is None:
                    raise ValueError(
                        f"No matching strategy in response from agent {agent.name!r}."
                    )
                agent.add_strategy(self.game.payoff_matrix.strategies[strategy_key])
                return strategy_key
        raise RuntimeError("Strategy retry loop exited unexpectedly")  # pragma: no cover

    def _execute_mixed_strategy(self, agent, prompt: str) -> str:
        """Ask the agent for a distribution and sample one strategy from it."""
        retrying = Retrying(
            stop=stop_after_attempt(_strategy_max_attempts()),
            wait=wait_fixed(1),
            retry=retry_if_exception_type((ValueError, BeliefParseError)),
            reraise=True,
        )
        for attempt in retrying:
            with attempt:
                response = agent.execute_round(prompt)
                logger.debug("Agent %s mixed response: %s", agent.name, response)
                distribution = parse_belief(response, self.game.payoff_matrix.strategies)
                # Record the elicited distribution as well as the sampled action.
                self.game.history.update_round(
                    self.round_number,
                    agent.name,
                    {"mixed_distribution": distribution},
                )
                keys = list(distribution.keys())
                weights = list(distribution.values())
                strategy_key = self.game.rng.choices(keys, weights=weights, k=1)[0]
                agent.add_strategy(self.game.payoff_matrix.strategies[strategy_key])
                return strategy_key
        raise RuntimeError("Mixed-strategy retry loop exited unexpectedly")  # pragma: no cover

    def _match_strategy(self, response: str):
        normalised = response.lower()
        for key, label in self.game.payoff_matrix.strategies.items():
            if label.lower() in normalised:
                return key
        return None

    def _update_round_history(self) -> None:
        for agent in self.game.agents.values():
            self.game.history.update_round(
                self.round_number,
                agent.name,
                {
                    "strategy": agent.last_strategy(),
                    "score": agent.last_score(),
                },
            )
