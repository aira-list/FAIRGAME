"""Agent abstraction: a participant in a FAIRGAME simulation.

Two concrete subclasses:

* :class:`LLMAgent` — strategy chosen by an LLM call (the historical default).
* :class:`BaselineAgent` — strategy chosen by a deterministic
  :class:`BaselineStrategy` (TitForTat, AlwaysCooperate, GrimTrigger, …).

The :class:`Agent` ABC keeps the shared state (history, name, personality,
get_info) in one place and exposes :meth:`execute_round` for the round
runner. Callers who don't care which subclass they're dealing with go
through the polymorphic interface — no more ``if agent.baseline_strategy``
branching at the call site.

For backwards compatibility, calling :class:`Agent(...)` still works: the
constructor returns the right subclass based on whether a baseline is
supplied.
"""

from __future__ import annotations

import abc
from typing import Any, Dict, List, Optional

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

    def __new__(cls, *args, **kwargs):  # type: ignore[override]
        # When called as ``Agent(...)`` directly (legacy code path), pick
        # the right subclass based on whether a baseline_strategy was
        # supplied. Subclass calls (``LLMAgent(...)`` etc.) bypass this.
        if cls is Agent:
            baseline = kwargs.get("baseline_strategy")
            if baseline is not None:
                return object.__new__(BaselineAgent)
            return object.__new__(LLMAgent)
        return object.__new__(cls)

    def __init__(
        self,
        name: str,
        llm_service: str,
        personality: str,
        opponent_personality_prob: float,
        agent_type: Optional[str] = None,
        baseline_strategy=None,  # only meaningful for BaselineAgent
    ) -> None:
        self.name: str = name
        self.strategies: List[str] = []
        self.scores: List[float] = []
        self.llm_service: str = llm_service
        self.personality: str = personality
        self.opponent_personality_prob: float = opponent_personality_prob
        self.agent_type: Optional[str] = agent_type
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

    def get_info(self) -> Dict[str, Any]:
        info: Dict[str, Any] = {
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
    of building a prompt — see :class:`src.game_round.GameRound`.

    Two construction patterns are supported:

    * Legacy: ``BaselineAgent(name, llm_service, personality, prob,
      baseline_strategy=...)`` — matches the ``Agent`` parent signature.
    * Compact: ``BaselineAgent(name, strategy, personality, prob)`` —
      pass the strategy positionally; ``llm_service`` is auto-derived.
    """

    def __init__(
        self,
        name: str,
        llm_service_or_strategy=None,
        personality: str = "n/a",
        opponent_personality_prob: float = 0.0,
        agent_type: Optional[str] = None,
        baseline_strategy=None,
    ) -> None:
        # Allow the second positional to be EITHER the LLM-service string
        # (legacy layout, with baseline_strategy as kwarg) or the strategy
        # object directly (compact layout).
        if baseline_strategy is None and not isinstance(
            llm_service_or_strategy, str
        ):
            baseline_strategy = llm_service_or_strategy
            llm_service = (
                f"Baseline:{baseline_strategy.name}"
                if baseline_strategy is not None
                else "Baseline:unknown"
            )
        else:
            llm_service = llm_service_or_strategy or (
                f"Baseline:{baseline_strategy.name}" if baseline_strategy else ""
            )

        super().__init__(
            name=name,
            llm_service=llm_service,
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
