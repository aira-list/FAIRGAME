"""Aggregate a multi-seed results DataFrame into mean ± 95% CI per scalar metric.

The :class:`ResultsProcessor` already produces one row per (game, seed) tuple
with a ``seed`` column when multi-seed mode is on. This module collapses
those rows into one row per game configuration, with mean and confidence
interval for every numeric scalar metric.
"""

from __future__ import annotations

import math
from typing import Iterable, List

import pandas as pd

# Identifying columns whose values define a "configuration" — multi-seed
# rows that match on all of these are aggregated together.
_DEFAULT_GROUPING = (
    "language",
    "agent1_personality",
    "agent2_personality",
    "agent1_llm",
    "agent2_llm",
)


def _ci_half_width(
    values: List[float],
    confidence: float = 0.95,
    use_t: bool = False,
) -> float:
    """Half-width of a confidence interval for the sample mean.

    Args:
        values: sample values.
        confidence: confidence level (e.g. 0.95).
        use_t: if True, use the t-distribution with ``n-1`` degrees of
            freedom (small-sample-correct). Otherwise use the
            Normal-approximation z-statistic (faster, slightly liberal
            for ``n < 30``). Default False preserves backwards-compat.
    """
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / (n - 1)
    standard_error = math.sqrt(variance / n)
    if use_t:
        try:
            from scipy import stats  # type: ignore

            critical = float(stats.t.ppf((1 + confidence) / 2, df=n - 1))
        except ImportError:  # pragma: no cover
            critical = (
                1.959964 if math.isclose(confidence, 0.95) else _normal_inverse(confidence)
            )
    else:
        critical = (
            1.959964 if math.isclose(confidence, 0.95) else _normal_inverse(confidence)
        )
    return critical * standard_error


def _normal_inverse(confidence: float) -> float:
    # Beasley-Springer approximation; sufficient for confidence in (0.5, 0.999).
    p = 1 - (1 - confidence) / 2
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    q = p - 0.5
    if abs(q) <= 0.425:
        r = q * q
        return q * (((((a[0]*r + a[1])*r + a[2])*r + a[3])*r + a[4])*r + a[5]) / (
            ((((b[0]*r + b[1])*r + b[2])*r + b[3])*r + b[4])*r + 1
        )
    r = math.sqrt(-math.log(min(p, 1 - p)))
    return (1 if q > 0 else -1) * r


def aggregate_seeds(
    df: pd.DataFrame,
    grouping_columns: Iterable[str] | None = None,
    confidence: float = 0.95,
    use_t: bool = False,
) -> pd.DataFrame:
    """Collapse a multi-seed DataFrame into mean ± CI per scalar column.

    Args:
        df: DataFrame produced by ``ResultsProcessor.process``.
        grouping_columns: Columns that together identify a configuration.
            Defaults to the standard ``(language, agent1_personality,
            agent2_personality, agent1_llm, agent2_llm)`` tuple. Columns
            absent from ``df`` are dropped silently.
        confidence: CI confidence level (default 0.95).

    Returns:
        A new DataFrame with one row per configuration. Each numeric column
        ``X`` becomes ``X_mean`` plus ``X_ci_half_width``; non-numeric
        columns are kept only when constant within the group.
    """
    if "seed" not in df.columns or len(df) == 0:
        return df.copy()

    cols = list(grouping_columns) if grouping_columns is not None else list(_DEFAULT_GROUPING)
    grouping = [c for c in cols if c in df.columns]
    if not grouping:
        # Nothing to group on — return the input untouched so the caller
        # gets the per-seed rows back.
        return df.copy()

    rows: List[dict] = []
    for keys, sub in df.groupby(grouping, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        out = dict(zip(grouping, keys))
        out["n_seeds"] = len(sub)
        for column in sub.columns:
            if column in grouping or column == "seed":
                continue
            series = sub[column]
            if _is_listy(series):
                # Don't try to dedup or aggregate list-valued cells.
                continue
            numeric = pd.to_numeric(series, errors="coerce")
            if numeric.notna().all():
                values = [float(v) for v in numeric.tolist()]
                mean = sum(values) / len(values)
                out[f"{column}_mean"] = mean
                out[f"{column}_ci_half_width"] = _ci_half_width(
                    values, confidence, use_t=use_t
                )
            else:
                non_null = series.dropna()
                try:
                    unique = non_null.unique().tolist()
                except TypeError:
                    continue
                if len(unique) == 1:
                    out[column] = unique[0]
        rows.append(out)
    return pd.DataFrame(rows)


def _is_listy(series: pd.Series) -> bool:
    """A column whose first non-null entry is a list / dict / tuple."""
    for v in series.dropna():
        return isinstance(v, (list, dict, tuple))
    return False
