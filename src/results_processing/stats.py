"""Hypothesis-test helpers for comparing two FAIRGAME runs on a metric.

Use case: you ran the same scenario twice (once at ToM order 0, once at
order 2) with multiple seeds, and you want a statistical answer to "did
ToM order make a difference?".

Provides:

* :func:`compare_metric` — Welch's t-test (parametric) plus a
  Mann–Whitney U test (rank-based, distribution-free).
* :func:`extract_numeric` — pull a numeric column out of a results
  DataFrame, dropping non-finite values.

Both tests are computed because Welch is more powerful when assumptions
hold and Mann–Whitney is robust when they don't. Reporting both lets the
researcher reach for whichever the reviewers prefer.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List

import pandas as pd


@dataclass
class ComparisonResult:
    metric: str
    n_a: int
    n_b: int
    mean_a: float
    mean_b: float
    mean_diff: float
    welch_t: float | None
    welch_p: float | None
    mannwhitney_u: float | None
    mannwhitney_p: float | None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def extract_numeric(df: pd.DataFrame, column: str) -> List[float]:
    """Pull ``column`` out of ``df`` as a list of floats, dropping NaN/non-numeric."""
    if column not in df.columns:
        return []
    series = pd.to_numeric(df[column], errors="coerce").dropna()
    return [float(v) for v in series.tolist()]


def compare_metric(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    metric: str,
) -> ComparisonResult:
    """Compare ``metric`` between two DataFrames with Welch + Mann–Whitney.

    Both tests are two-sided. Returns ``None`` for the test statistic and
    p-value when the underlying ``scipy`` call fails (typically because
    one of the samples is empty or has zero variance).
    """
    a = extract_numeric(df_a, metric)
    b = extract_numeric(df_b, metric)

    welch_t = welch_p = None
    mw_u = mw_p = None

    try:
        from scipy import stats  # type: ignore
    except ImportError:
        stats = None  # type: ignore

    if stats is not None and a and b:
        try:
            t_res = stats.ttest_ind(a, b, equal_var=False)
            welch_t = float(t_res.statistic)
            welch_p = float(t_res.pvalue)
        except Exception:  # noqa: BLE001 — scipy edge cases
            pass
        try:
            u_res = stats.mannwhitneyu(a, b, alternative="two-sided")
            mw_u = float(u_res.statistic)
            mw_p = float(u_res.pvalue)
        except Exception:  # noqa: BLE001
            pass

    mean_a = sum(a) / len(a) if a else float("nan")
    mean_b = sum(b) / len(b) if b else float("nan")
    return ComparisonResult(
        metric=metric,
        n_a=len(a),
        n_b=len(b),
        mean_a=mean_a,
        mean_b=mean_b,
        mean_diff=mean_a - mean_b,
        welch_t=welch_t,
        welch_p=welch_p,
        mannwhitney_u=mw_u,
        mannwhitney_p=mw_p,
    )


def compare_metrics(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    metrics: Iterable[str],
) -> pd.DataFrame:
    """Run :func:`compare_metric` over many metrics, return a DataFrame."""
    rows: List[Dict[str, Any]] = []
    for metric in metrics:
        rows.append(compare_metric(df_a, df_b, metric).to_dict())
    return pd.DataFrame(rows)


def default_comparison_metrics(df: pd.DataFrame) -> List[str]:
    """Pick a reasonable default set of scalar metrics to compare."""
    candidates = [
        "welfare_mean_sum",
        "welfare_mean_min",
        "welfare_mean_gini",
        "welfare_efficiency",
        "equilibrium_rate",
        "agent1_belief_mean_brier",
        "agent2_belief_mean_brier",
        "agent1_regret_mean",
        "agent2_regret_mean",
    ]
    return [c for c in candidates if c in df.columns]
