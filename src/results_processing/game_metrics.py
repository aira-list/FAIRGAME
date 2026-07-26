"""Round-level analysis: equilibrium membership and welfare measures.

These helpers operate on the flat per-round data the results processor
already builds (per-agent strategy and score lists). They live in
``results_processing`` because they're computed during DataFrame assembly,
not during the live game loop.
"""

from __future__ import annotations

from collections.abc import Sequence

# ---- Equilibrium ---------------------------------------------------------


def equilibrium_metrics(
    combination_keys_per_round: Sequence[str | None],
    equilibria: Sequence[str],
) -> dict[str, float | None]:
    """Per-game equilibrium-distance metrics.

    Args:
        combination_keys_per_round: Combination key (e.g. ``"combination4"``)
            played each round, or ``None`` for rounds we couldn't resolve.
        equilibria: Combination keys the user has declared to be equilibria.

    Returns:
        A dict with::

            equilibrium_rate        # fraction of resolved rounds at equilibrium
            equilibrium_per_round   # list of {True, False, None}
            first_equilibrium_round # 1-based round, or None if never observed
    """
    eq_set = set(equilibria)
    per_round: list[bool | None] = []
    for key in combination_keys_per_round:
        if key is None:
            per_round.append(None)
        else:
            per_round.append(key in eq_set)

    valid = [v for v in per_round if v is not None]
    rate = (sum(1 for v in valid if v) / len(valid)) if valid else None
    first_round: int | None = next((i + 1 for i, v in enumerate(per_round) if v is True), None)
    return {
        "equilibrium_rate": rate,
        "equilibrium_per_round": per_round,
        "first_equilibrium_round": first_round,
    }


# ---- Welfare -------------------------------------------------------------


def gini_coefficient(values: Sequence[float]) -> float:
    """Standard Gini coefficient.

    Returns 0 for perfect equality and approaches 1 with extreme inequality.
    Negative values are shifted so the formula is well-defined; the shift
    only affects scale, not the relative ordering between rounds.
    """
    n = len(values)
    if n == 0:
        return 0.0
    shift = -min(values) + 1e-9 if min(values) < 0 else 0.0
    sorted_vals = sorted(v + shift for v in values)
    cumulative = 0.0
    for i, v in enumerate(sorted_vals, start=1):
        cumulative += i * v
    total = sum(sorted_vals)
    if total <= 0:
        return 0.0
    return (2 * cumulative) / (n * total) - (n + 1) / n


def welfare_round_metrics(round_payoffs: Sequence[float]) -> dict[str, float]:
    """Utilitarian / Rawlsian / Gini metrics for one round."""
    payoffs = [float(p) for p in round_payoffs]
    if not payoffs:
        return {"sum": 0.0, "mean": 0.0, "min": 0.0, "max": 0.0, "gini": 0.0}
    return {
        "sum": sum(payoffs),
        "mean": sum(payoffs) / len(payoffs),
        "min": min(payoffs),
        "max": max(payoffs),
        "gini": gini_coefficient(payoffs),
    }


def welfare_summary(
    per_agent_scores: dict[str, Sequence[float]],
    pareto_optimal_sum: float | None = None,
    direction: str = "reward",
) -> dict[str, float | None]:
    """Aggregate welfare stats across the rounds of one game.

    Args:
        per_agent_scores: ``{agent_name: [score_round_1, ...]}``.
        pareto_optimal_sum: If given, ``efficiency`` = mean(round-sum) /
            ``pareto_optimal_sum``; otherwise ``efficiency`` is ``None``.
        direction: the config's ``payoffDirection``. For ``"penalty"``
            weights (lower is better) the ratio is inverted —
            ``pareto_optimal_sum`` is then the *lowest* achievable cell sum
            and ``efficiency`` = pareto_optimal_sum / mean(round-sum) — so 1
            still means "as good as the Pareto-optimal cell" either way.
    """
    rounds = _zip_rounds(per_agent_scores)
    if not rounds:
        return {
            "welfare_mean_sum": None,
            "welfare_mean_min": None,
            "welfare_mean_gini": None,
            "welfare_efficiency": None,
            "welfare_per_round": [],
        }
    per_round = [welfare_round_metrics(round_) for round_ in rounds]
    n = len(per_round)
    mean_sum = sum(r["sum"] for r in per_round) / n
    if direction == "penalty":
        efficiency = pareto_optimal_sum / mean_sum if pareto_optimal_sum and mean_sum else None
    else:
        efficiency = (
            mean_sum / pareto_optimal_sum
            if pareto_optimal_sum and pareto_optimal_sum != 0
            else None
        )
    return {
        "welfare_mean_sum": mean_sum,
        "welfare_mean_min": sum(r["min"] for r in per_round) / n,
        "welfare_mean_gini": sum(r["gini"] for r in per_round) / n,
        "welfare_efficiency": efficiency,
        "welfare_per_round": per_round,
    }


def _zip_rounds(per_agent_scores: dict[str, Sequence[float]]) -> list[list[float]]:
    """Transpose ``{agent: [round1, round2]}`` into ``[[r1_a, r1_b], [r2_a, r2_b]]``."""
    if not per_agent_scores:
        return []
    n_rounds = min(len(scores) for scores in per_agent_scores.values())
    return [[float(scores[r]) for scores in per_agent_scores.values()] for r in range(n_rounds)]
