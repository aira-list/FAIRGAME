"""Aggregate metrics for the costly-monitoring (trust) mechanism."""

from __future__ import annotations

from typing import Any

from src.communication.trust import LOOK


def trust_summary(
    trust_actions: list[str | None], trust_costs: list[float | None]
) -> dict[str, Any]:
    """Per-agent monitoring metrics over a game.

    Returns the ``look_rate`` (fraction of decided rounds the agent paid to
    ``LOOK``) and the ``monitoring_cost_total`` (sum of costs incurred).
    Rounds with no recorded decision are ignored for the rate.

    ``look_count``/``no_look_count``/``look_ratio``/``total_trust_cost`` are
    the FAIRGAME-Trust (Powell et al.) spellings of the same quantities,
    carried so analyses written against the fork keep working.
    """
    decided = [a for a in trust_actions if a]
    looks = sum(1 for a in decided if a == LOOK)
    look_rate = (looks / len(decided)) if decided else None
    cost_total = float(sum(c for c in trust_costs if c is not None))
    return {
        "look_rate": look_rate,
        "monitoring_cost_total": cost_total,
        "looks": looks,
        "decided_rounds": len(decided),
        "look_count": looks,
        "no_look_count": len(decided) - looks,
        "look_ratio": look_rate,
        "total_trust_cost": cost_total,
    }
