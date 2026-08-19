"""Agent abstraction: a participant in a FAIRGAME simulation.

Two concrete subclasses, constructed explicitly by the factory:

* :class:`LLMAgent` — strategy chosen by an LLM call.
* :class:`BaselineAgent` — strategy chosen by a deterministic
  :class:`BaselineStrategy` (TitForTat, AlwaysCooperate, GrimTrigger, …).

The :class:`Agent` ABC keeps the shared state (history, name, personality,
get_info) in one place and exposes :meth:`execute_round` for the round
runner. Callers who don't care which subclass they're dealing with go
through the polymorphic interface — no ``if agent.baseline_strategy``
branching at the call site.
"""

from __future__ import annotations

import abc
from typing import Any

from src.llm_connectors import execute_prompt
from src.utils.logger import get_logger

logger = get_logger(__name__)


class Agent(abc.ABC):
    """Abstract base class for game participants.

    Stores the per-game history (strategies, scores), identity, and ToM
    metadata (agent_type, opponent_personality_prob). Subclasses
    implement :meth:`execute_round` to source a strategy from the
    appropriate decision-maker (LLM or baseline).
    """

    def __init__(
        self,
        name: str,
        llm_service: str,
        personality: str,
        opponent_personality_prob: float,
        agent_type: str | None = None,
        baseline_strategy=None,  # only meaningful for BaselineAgent
    ) -> None:
        self.name: str = name
        self.strategies: list[str] = []
        self.scores: list[float] = []
        self.llm_service: str = llm_service
        self.personality: str = personality
        self.opponent_personality_prob: float = opponent_personality_prob
        self.agent_type: str | None = agent_type
        self.baseline_strategy = baseline_strategy

    # ---- History ---------------------------------------------------------

    def add_strategy(self, strategy: str) -> None:
        logger.debug("Agent %s chose strategy %s", self.name, strategy)
        self.strategies.append(strategy)

    def last_strategy(self) -> str:
        return self.strategies[-1]

    def add_score(self, score: float) -> None:
        self.scores.append(score)

    def last_score(self) -> float:
        return self.scores[-1]

    # ---- Identity --------------------------------------------------------

    def get_info(self) -> dict[str, Any]:
        info: dict[str, Any] = {
            "name": self.name,
            "llm_service": self.llm_service,
            "personality": self.personality,
            "opponent_personality_probability": self.opponent_personality_prob,
        }
        if self.agent_type is not None:
            info["agent_type"] = self.agent_type
        if self.baseline_strategy is not None:
            info["baseline_strategy"] = self.baseline_strategy.name
        return info

    # ---- Decision (subclass-specific) -----------------------------------

    @abc.abstractmethod
    def execute_round(self, prompt: str) -> str:
        """Source a response (raw LLM output, or sentinel) for this round."""


class LLMAgent(Agent):
    """A participant whose decisions are made by an LLM call."""

    def execute_round(self, prompt: str) -> str:
        return execute_prompt(self.llm_service, prompt)


class BaselineAgent(Agent):
    """A participant whose decisions come from a :class:`BaselineStrategy`.

    The round runner spots a ``BaselineAgent`` and routes through
    ``agent.baseline_strategy.choose(agent, game, round_number)`` instead
    of building a prompt — see :class:`src.game.game_round.GameRound`.

    Construction: ``BaselineAgent(name, strategy, personality, prob)`` —
    the strategy object is the second positional; ``llm_service`` is
    derived from it (``"Baseline:<strategy name>"``) unless overridden,
    so results columns still show which baseline played.
    """

    def __init__(
        self,
        name: str,
        baseline_strategy,
        personality: str = "n/a",
        opponent_personality_prob: float = 0.0,
        agent_type: str | None = None,
        llm_service: str | None = None,
    ) -> None:
        super().__init__(
            name=name,
            llm_service=llm_service or f"Baseline:{baseline_strategy.name}",
            personality=personality,
            opponent_personality_prob=opponent_personality_prob,
            agent_type=agent_type,
            baseline_strategy=baseline_strategy,
        )

    def execute_round(self, prompt: str) -> str:
        raise NotImplementedError(
            "BaselineAgent.execute_round is never called; the round "
            "runner invokes baseline_strategy.choose() directly. If you "
            "see this error, the round runner forgot to dispatch on agent "
            "type."
        )
