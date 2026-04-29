"""Per-round best-response and regret computation.

After a round is played, each agent's "regret" is the gap between the
payoff it actually got and the highest payoff it *could* have got given
the opponents' realised moves. A rational agent in a one-shot game has
zero regret on average; persistently positive regret indicates the agent
is leaving money on the table.

These helpers operate on the lightweight ``payoff_matrix_summary`` that
results processing already retains, so they don't need access to the
full :class:`PayoffMatrix` instance from the engine.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence


def best_response_payoff(
    matrix_summary: Dict[str, Any],
    language: str,
    agent_index: int,
    other_strategies: Sequence[str],
) -> Optional[float]:
    """Maximum payoff agent ``agent_index`` could have earned this round.

    Args:
        matrix_summary: ``{"strategies": {...}, "combinations": {...}, "matrix": {...}}``
            (all four blocks are required — the strict ``payoff_matrix``
            shape, not the ``payoff_matrix_summary`` slim form).
        language: Language key used to read display labels.
        agent_index: 0-based index of the agent whose best response we want.
        other_strategies: The strategy *labels* the other agents played.
            Position ``i`` is the i-th opponent in the canonical agent order.

    Returns:
        The payoff under the agent's best response. ``None`` when the
        matrix isn't fully resolvable (e.g. a custom payoff function that
        wasn't expanded into a matrix).
    """
    strategies = (matrix_summary.get("strategies") or {}).get(language) or {}
    combinations = matrix_summary.get("combinations") or {}
    weight_matrix = matrix_summary.get("matrix") or {}
    weights = matrix_summary.get("weights") or {}
    if not strategies or not combinations or not weight_matrix or not weights:
        return None

    label_to_key = {label: key for key, label in strategies.items()}
    other_keys = [label_to_key.get(label) for label in other_strategies]
    if any(k is None for k in other_keys):
        return None

    combo_lookup = {tuple(v): k for k, v in combinations.items()}

    best: Optional[float] = None
    # ``strategies`` is keyed by canonical strategy key (e.g. ``strategy1``).
    for own_key in strategies.keys():
        full_choice = list(other_keys)
        full_choice.insert(agent_index, own_key)
        combo_key = combo_lookup.get(tuple(full_choice))
        if combo_key is None:
            continue
        weight_keys = weight_matrix.get(combo_key)
        if not weight_keys or agent_index >= len(weight_keys):
            continue
        payoff = float(weights.get(weight_keys[agent_index], 0))
        if best is None or payoff > best:
            best = payoff
    return best


def regret_per_round(
    matrix_summary: Dict[str, Any],
    language: str,
    agent_index: int,
    own_strategies: Sequence[str],
    own_scores: Sequence[float],
    others_strategies_per_round: Sequence[Sequence[str]],
) -> List[Optional[float]]:
    """Per-round regret for one agent.

    Returns ``None`` for any round we couldn't resolve (missing strategy
    label, payoff function not expanded, etc.).
    """
    out: List[Optional[float]] = []
    for r, own_label in enumerate(own_strategies):
        if r >= len(others_strategies_per_round) or r >= len(own_scores):
            out.append(None)
            continue
        best = best_response_payoff(
            matrix_summary, language, agent_index, others_strategies_per_round[r]
        )
        if best is None:
            out.append(None)
            continue
        try:
            actual = float(own_scores[r])
        except (TypeError, ValueError):
            out.append(None)
            continue
        out.append(max(0.0, best - actual))
    return out
