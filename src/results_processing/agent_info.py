"""Static, per-agent metadata flattened into the results DataFrame."""

from __future__ import annotations

from typing import Any, Dict, Optional


class AgentInfo:
    """Metadata for a single agent.

    Stores everything that is constant across rounds — name, LLM service,
    personality, opponent prior, plus optional fields for the Bayesian-game
    type system and the canonical baseline strategy library.
    """

    def __init__(
        self,
        name: str,
        llm_service: str,
        personality: str,
        opponent_prob: float,
        agent_type: Optional[str] = None,
        baseline_strategy: Optional[str] = None,
    ) -> None:
        self.name = name
        self.llm_service = llm_service
        self.personality = personality
        self.opponent_personality_probability = opponent_prob
        self.agent_type = agent_type
        self.baseline_strategy = baseline_strategy

    def to_dict(self, prefix: str) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            f"{prefix}name": self.name,
            f"{prefix}llm": self.llm_service,
            f"{prefix}personality": self.personality,
            f"{prefix}knows_opponent_with_prob": self.opponent_personality_probability,
        }
        if self.agent_type is not None:
            out[f"{prefix}agent_type"] = self.agent_type
        if self.baseline_strategy is not None:
            out[f"{prefix}baseline_strategy"] = self.baseline_strategy
        return out
