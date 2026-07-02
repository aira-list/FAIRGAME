"""Per-round best-response and regret computation.

After a round is played, each agent's "regret" is the gap between the
payoff it actually got and the highest payoff it *could* have got given
the opponents' realised moves. A rational agent in a one-shot game has
zero regret on average; persistently positive regret indicates the agent
is leaving money on the table.

Both sides of the comparison are resolved from the **raw payoff matrix**.
Recorded history scores are deliberately not used: they are post-transform
values (utility transforms, discounting, trust look-costs), and comparing
them against raw matrix payoffs would systematically inflate regret.

These helpers operate on the lightweight ``payoff_matrix_summary`` that
results processing already retains, so they don't need access to the
full :class:`PayoffMatrix` instance from the engine.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from src.game.payoff_matrix import label_to_key_map


def _matrix_blocks(
    matrix_summary: dict[str, Any], language: str
) -> tuple[dict[str, str], dict[tuple[str, ...], str], dict[str, Any], dict[str, Any]] | None:
    """Validate and unpack the matrix summary; ``None`` if not resolvable."""
    strategies = (matrix_summary.get("strategies") or {}).get(language) or {}
    combinations = matrix_summary.get("combinations") or {}
    weight_matrix = matrix_summary.get("matrix") or {}
    weights = matrix_summary.get("weights") or {}
    if not strategies or not combinations or not weight_matrix or not weights:
        return None
    combo_lookup = {tuple(v): k for k, v in combinations.items()}
    return strategies, combo_lookup, weight_matrix, weights


def _combination_payoff(
    blocks: tuple[dict[str, str], dict[tuple[str, ...], str], dict[str, Any], dict[str, Any]],
    agent_index: int,
    own_key: str,
    other_keys: Sequence[str],
) -> float | None:
    """Raw matrix payoff for ``agent_index`` in one strategy combination."""
    _, combo_lookup, weight_matrix, weights = blocks
    full_choice = list(other_keys)
    full_choice.insert(agent_index, own_key)
    combo_key = combo_lookup.get(tuple(full_choice))
    if combo_key is None:
        return None
    weight_keys = weight_matrix.get(combo_key)
    if not weight_keys or agent_index >= len(weight_keys):
        return None
    return float(weights.get(weight_keys[agent_index], 0))


def _other_keys(
    blocks: tuple[dict[str, str], dict[tuple[str, ...], str], dict[str, Any], dict[str, Any]],
    other_strategies: Sequence[str],
) -> list[str] | None:
    strategies = blocks[0]
    label_to_key = label_to_key_map(strategies)
    keys = [label_to_key.get(label) for label in other_strategies]
    if any(k is None for k in keys):
        return None
    return keys  # type: ignore[return-value]


def best_response_payoff(
    matrix_summary: dict[str, Any],
    language: str,
    agent_index: int,
    other_strategies: Sequence[str],
) -> float | None:
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
    blocks = _matrix_blocks(matrix_summary, language)
    if blocks is None:
        return None
    other_keys = _other_keys(blocks, other_strategies)
    if other_keys is None:
        return None

    # Strict completeness check: if ANY alternative-strategy combination
    # is missing from the matrix, fail closed rather than under-stating
    # the agent's best-response payoff.
    best: float | None = None
    for own_key in blocks[0]:
        payoff = _combination_payoff(blocks, agent_index, own_key, other_keys)
        if payoff is None:
            return None
        if best is None or payoff > best:
            best = payoff
    return best


def played_payoff(
    matrix_summary: dict[str, Any],
    language: str,
    agent_index: int,
    own_strategy: str,
    other_strategies: Sequence[str],
) -> float | None:
    """Raw matrix payoff the agent actually earned given everyone's labels."""
    blocks = _matrix_blocks(matrix_summary, language)
    if blocks is None:
        return None
    strategies = blocks[0]
    label_to_key = label_to_key_map(strategies)
    own_key = label_to_key.get(own_strategy)
    other_keys = _other_keys(blocks, other_strategies)
    if own_key is None or other_keys is None:
        return None
    return _combination_payoff(blocks, agent_index, own_key, other_keys)


def regret_per_round(
    matrix_summary: dict[str, Any],
    language: str,
    agent_index: int,
    own_strategies: Sequence[str],
    others_strategies_per_round: Sequence[Sequence[str]],
) -> list[float | None]:
    """Per-round regret for one agent, in raw payoff-matrix units.

    Returns ``None`` for any round we couldn't resolve (missing strategy
    label, payoff function not expanded, etc.).
    """
    out: list[float | None] = []
    for r, own_label in enumerate(own_strategies):
        if r >= len(others_strategies_per_round):
            out.append(None)
            continue
        others = others_strategies_per_round[r]
        best = best_response_payoff(matrix_summary, language, agent_index, others)
        actual = played_payoff(matrix_summary, language, agent_index, own_label, others)
        if best is None or actual is None:
            out.append(None)
            continue
        out.append(max(0.0, best - actual))
    return out
