"""Agent abstraction: a participant that talks to an LLM provider."""

from __future__ import annotations

from typing import Any, Dict, List

from src.llm_connectors import execute_prompt
from src.utils.logger import get_logger

logger = get_logger(__name__)


class Agent:
    """A single participant in a FAIRGAME simulation.

    Each agent stores its own move history and delegates strategy selection to
    the configured LLM service.
    """

    def __init__(
        self,
        name: str,
        llm_service: str,
        personality: str,
        opponent_personality_prob: float,
        agent_type: str | None = None,
        baseline_strategy=None,
    ) -> None:
        self.name: str = name
        self.strategies: List[str] = []
        self.scores: List[int] = []
        self.llm_service: str = llm_service
        self.personality: str = personality
        self.opponent_personality_prob: float = opponent_personality_prob
        self.agent_type: str | None = agent_type
        self.baseline_strategy = baseline_strategy

    def execute_round(self, prompt: str) -> str:
        """Send ``prompt`` to the configured LLM and return its raw response."""
        return execute_prompt(self.llm_service, prompt)

    def add_strategy(self, strategy: str) -> None:
        """Append a strategy choice to the agent's history."""
        logger.debug("Agent %s chose strategy %s", self.name, strategy)
        self.strategies.append(strategy)

    def last_strategy(self) -> str:
        return self.strategies[-1]

    def add_score(self, score: int) -> None:
        self.scores.append(score)

    def last_score(self) -> int:
        return self.scores[-1]

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
