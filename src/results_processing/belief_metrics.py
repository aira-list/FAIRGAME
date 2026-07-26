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

from collections.abc import Iterable, Mapping, Sequence


def brier_score(
    belief: Mapping[str, float], outcome_key: str, *, sum_tolerance: float = 0.02
) -> float:
    """Compute the multi-class Brier score for a single forecast.

    ``belief`` must be a probability distribution (non-negative entries that
    sum to ~1). Passing raw logits / unnormalised weights would otherwise
    yield a finite-but-meaningless score silently.
    """
    if not belief:
        raise ValueError("Cannot compute Brier score for an empty belief.")
    probs = [float(p) for p in belief.values()]
    if any(p < -sum_tolerance or p > 1.0 + sum_tolerance for p in probs):
        raise ValueError(f"Belief contains non-probability values: {dict(belief)!r}.")
    total = sum(probs)
    if abs(total - 1.0) > sum_tolerance:
        raise ValueError(
            f"Belief probabilities sum to {total:.3f}, expected ~1.0 "
            "(pass a normalised distribution)."
        )
    score = 0.0
    for key, prob in belief.items():
        target = 1.0 if key == outcome_key else 0.0
        score += (float(prob) - target) ** 2
    return score


def belief_agreement(belief: Mapping[str, float], outcome_key: str) -> bool:
    """Return ``True`` when the modal-probability strategy matches reality.

    Ties are never agreement: a 50/50 forecast expresses no modal prediction,
    and breaking the tie by dict insertion order would credit it half the
    time purely by key order.
    """
    if not belief:
        return False
    top = max(float(v) for v in belief.values())
    modal = [k for k, v in belief.items() if float(v) == top]
    return len(modal) == 1 and modal[0] == outcome_key


def per_round_metrics(
    beliefs: Sequence[Mapping[str, float] | None],
    opponent_strategies: Sequence[str | None],
) -> list[dict[str, float] | None]:
    """Pair-wise belief vs realised-outcome metrics, round by round.

    Returns ``None`` for rounds where the belief is missing (parse failed)
    or the opponent strategy is missing (game stopped early).
    """
    out: list[dict[str, float] | None] = []
    for belief, outcome in zip(beliefs, opponent_strategies, strict=False):
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


def brier_score_distribution(
    predicted: Mapping[str, float],
    target: Mapping[str, float],
) -> float:
    """Brier score with a *soft* target distribution, not a one-hot.

    Generalises :func:`brier_score` to the second-order belief case:
    we score one probability distribution (the agent's prediction of
    its opponent's belief) against another (the opponent's actual
    belief). Reduces exactly to the classic Brier score when ``target``
    is a one-hot vector.

    Defensive against missing keys: any key present on one side but
    not the other is treated as having probability 0 on the missing
    side.
    """
    keys = set(predicted) | set(target)
    score = 0.0
    for k in keys:
        score += (float(predicted.get(k, 0.0)) - float(target.get(k, 0.0))) ** 2
    return score


def per_round_second_order_metrics(
    agent_second_order_beliefs: Sequence[Mapping[str, float] | None],
    opponent_first_order_beliefs: Sequence[Mapping[str, float] | None],
) -> list[dict[str, float] | None]:
    """Per-round 2nd-order Brier paired with the opponent's 1st-order belief.

    The agent's 2nd-order belief is its prediction of what its
    opponent thinks. The opponent's actual 1st-order belief from the
    same round is the ground truth.

    Returns ``None`` for any round where either side is missing.
    """
    out: list[dict[str, float] | None] = []
    for predicted, target in zip(
        agent_second_order_beliefs,
        opponent_first_order_beliefs,
        strict=False,
    ):
        if not predicted or not target:
            out.append(None)
            continue
        out.append({"brier": brier_score_distribution(predicted, target)})
    return out


def aggregate_metrics(per_round: Iterable[dict[str, float] | None]) -> dict[str, float | None]:
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
