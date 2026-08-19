"""Static, per-agent metadata flattened into the results DataFrame."""

from __future__ import annotations

from typing import Any

from src.results_processing.row_schema import AgentCol


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
        agent_type: str | None = None,
        baseline_strategy: str | None = None,
    ) -> None:
        self.name = name
        self.llm_service = llm_service
        self.personality = personality
        self.opponent_personality_probability = opponent_prob
        self.agent_type = agent_type
        self.baseline_strategy = baseline_strategy

    def to_dict(self, prefix: str) -> dict[str, Any]:
        out: dict[str, Any] = {
            prefix + AgentCol.NAME: self.name,
            prefix + AgentCol.LLM: self.llm_service,
            prefix + AgentCol.PERSONALITY: self.personality,
            prefix + AgentCol.KNOWS_OPPONENT_WITH_PROB: self.opponent_personality_probability,
        }
        if self.agent_type is not None:
            out[prefix + AgentCol.AGENT_TYPE] = self.agent_type
        if self.baseline_strategy is not None:
            out[prefix + AgentCol.BASELINE_STRATEGY] = self.baseline_strategy
        return out
