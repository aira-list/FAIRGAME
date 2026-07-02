"""The results-row contract — one authoritative place for column names.

``ResultsProcessor`` emits one **row** per game as a flat dict. Rows travel:
engine -> ``/run`` response (native types) and engine -> ``rows.json`` on disk
-> the Results dashboard and Compare views. Because the columns are keyed by
plain strings, the producer (:mod:`src.results_processing.game_data`,
:mod:`~.agent_info`, the metric helpers) and the consumers
(:mod:`web_api.dashboards`, :mod:`web_api.compare`) must agree on the names.
This module is that agreement: rename a column here and both sides move
together, instead of a chart silently going blank.

Row shape
=========

Game-level columns (always present unless noted) — see :class:`Col`::

    game_id, language, n_rounds_is_known, max_rounds, played_rounds,
    agents_communicate, elicit_beliefs, tom_order
    seed                 (only when the run fixed a seed)
    payoff_variant_name  (only for a configuration-group variant)
    welfare_* / equilibrium_*  (game-theoretic aggregates)

Per-agent columns are prefixed ``agent{i}_`` for ``i = 1..N`` in canonical
agent order; build the name with :func:`agent_col`. See :class:`AgentCol`
for the field names. List-valued fields (one entry per played round) are
listed in :data:`AGENT_LIST_FIELDS`; everything else is a scalar.
"""

from __future__ import annotations

from typing import Any


def agent_col(index: int, field: str) -> str:
    """Column name for a per-agent field: ``agent_col(1, AgentCol.SCORES)``."""
    return f"agent{index}_{field}"


class AgentCol:
    """Per-agent field names (the part after the ``agent{i}_`` prefix)."""

    # Identity / configuration (from AgentInfo.to_dict)
    NAME = "name"
    LLM = "llm"
    PERSONALITY = "personality"
    KNOWS_OPPONENT_WITH_PROB = "knows_opponent_with_prob"
    AGENT_TYPE = "agent_type"
    BASELINE_STRATEGY = "baseline_strategy"

    # Per-round play (list-valued)
    STRATEGIES = "strategies"
    SCORES = "scores"
    MESSAGES = "messages"

    # Belief elicitation (Theory of Mind)
    BELIEFS = "beliefs"
    BELIEFS_2ND_ORDER = "beliefs_2nd_order"
    BELIEF_BRIER_PER_ROUND = "belief_brier_per_round"  # list
    BELIEF_MEAN_BRIER = "belief_mean_brier"
    BELIEF_MEAN_P_OUTCOME = "belief_mean_p_outcome"
    BELIEF_AGREEMENT_RATE = "belief_agreement_rate"
    BELIEF_2ND_ORDER_PER_ROUND_BRIER = "belief_2nd_order_per_round_brier"  # list
    BELIEF_2ND_ORDER_MEAN_BRIER = "belief_2nd_order_mean_brier"

    # Trust / costly monitoring
    TRUST_ACTIONS = "trust_actions"  # list
    LOOK_RATE = "look_rate"
    MONITORING_COST_TOTAL = "monitoring_cost_total"

    # Regret
    REGRET_PER_ROUND = "regret_per_round"  # list
    REGRET_MEAN = "regret_mean"


# Per-agent fields whose value is a per-round list (vs. a scalar).
AGENT_LIST_FIELDS = frozenset(
    {
        AgentCol.STRATEGIES,
        AgentCol.SCORES,
        AgentCol.MESSAGES,
        AgentCol.BELIEFS,
        AgentCol.BELIEFS_2ND_ORDER,
        AgentCol.BELIEF_BRIER_PER_ROUND,
        AgentCol.BELIEF_2ND_ORDER_PER_ROUND_BRIER,
        AgentCol.TRUST_ACTIONS,
        AgentCol.REGRET_PER_ROUND,
    }
)


class Col:
    """Game-level (non-agent) column names."""

    GAME_ID = "game_id"
    LANGUAGE = "language"
    N_ROUNDS_IS_KNOWN = "n_rounds_is_known"
    MAX_ROUNDS = "max_rounds"
    PLAYED_ROUNDS = "played_rounds"
    AGENTS_COMMUNICATE = "agents_communicate"
    ELICIT_BELIEFS = "elicit_beliefs"
    TOM_ORDER = "tom_order"
    SEED = "seed"
    PAYOFF_VARIANT_NAME = "payoff_variant_name"


def is_missing(value: Any) -> bool:
    """Shared 'no value here' test for row cells (None / "" / NaN)."""
    if value is None or value == "":
        return True
    return isinstance(value, float) and value != value  # NaN
