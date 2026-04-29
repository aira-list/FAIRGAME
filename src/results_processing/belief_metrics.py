"""Belief-accuracy metrics for Theory-of-Mind experiments.

These helpers operate on history dicts produced by :class:`GameHistory` —
specifically on the ``belief`` field that the ``believe`` phase writes for
each agent each round, alongside the realised opponent strategies.

* Brier score (multi-class form): :math:`\\sum_k (p_k - \\mathbb{1}\\{outcome=k\\})^2`.
  Lower is better; 0 = perfect prediction; 2 = maximally wrong (all mass on
  the wrong outcome).
* Calibration: |stated probability of the realised outcome - 1.0|.
* Agreement: whether the strategy with the highest belief probability matches
  the opponent's actual choice.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Mapping, Optional, Sequence


def brier_score(belief: Mapping[str, float], outcome_key: str) -> float:
    """Compute the multi-class Brier score for a single forecast."""
    if not belief:
        raise ValueError("Cannot compute Brier score for an empty belief.")
    score = 0.0
    for key, prob in belief.items():
        target = 1.0 if key == outcome_key else 0.0
        score += (float(prob) - target) ** 2
    return score


def belief_agreement(belief: Mapping[str, float], outcome_key: str) -> bool:
    """Return ``True`` when the modal-probability strategy matches reality."""
    if not belief:
        return False
    top_key = max(belief.items(), key=lambda kv: float(kv[1]))[0]
    return top_key == outcome_key


def per_round_metrics(
    beliefs: Sequence[Optional[Mapping[str, float]]],
    opponent_strategies: Sequence[Optional[str]],
) -> List[Optional[Dict[str, float]]]:
    """Pair-wise belief vs realised-outcome metrics, round by round.

    Returns ``None`` for rounds where the belief is missing (parse failed)
    or the opponent strategy is missing (game stopped early).
    """
    out: List[Optional[Dict[str, float]]] = []
    for belief, outcome in zip(beliefs, opponent_strategies):
        if not belief or outcome is None:
            out.append(None)
            continue
        out.append(
            {
                "brier": brier_score(belief, outcome),
                "p_outcome": float(belief.get(outcome, 0.0)),
                "agreement": float(belief_agreement(belief, outcome)),
            }
        )
    return out


def aggregate_metrics(per_round: Iterable[Optional[Dict[str, float]]]) -> Dict[str, Optional[float]]:
    """Mean Brier, p(outcome), and agreement rate across non-empty rounds."""
    valid = [m for m in per_round if m is not None]
    if not valid:
        return {"mean_brier": None, "mean_p_outcome": None, "agreement_rate": None}
    n = len(valid)
    return {
        "mean_brier": sum(m["brier"] for m in valid) / n,
        "mean_p_outcome": sum(m["p_outcome"] for m in valid) / n,
        "agreement_rate": sum(m["agreement"] for m in valid) / n,
    }
