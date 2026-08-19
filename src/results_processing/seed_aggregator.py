"""Aggregate a multi-seed results DataFrame into mean ± 95% CI per scalar metric.

The :class:`ResultsProcessor` already produces one row per (game, seed) tuple
with a ``seed`` column when multi-seed mode is on. This module collapses
those rows into one row per game configuration, with mean and confidence
interval for every numeric scalar metric.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

import pandas as pd

# Identifying columns whose values define a "configuration" — multi-seed
# rows that match on all of these are aggregated together. Every axis a
# permutation/variant expansion can vary must be listed: leaving one out
# (e.g. the opponent-personality prior) silently pools rows from genuinely
# different treatments and averages the treatment variable itself. Columns
# absent from a given DataFrame are dropped at aggregation time.
_DEFAULT_GROUPING = (
    "language",
    "agent1_personality",
    "agent2_personality",
    "agent1_llm",
    "agent2_llm",
    "agent1_knows_opponent_with_prob",
    "agent2_knows_opponent_with_prob",
    "agent1_agent_type",
    "agent2_agent_type",
    "agent1_baseline_strategy",
    "agent2_baseline_strategy",
    "payoff_variant_name",
)


def _ci_half_width(
    values: list[float],
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
            critical = 1.959964 if math.isclose(confidence, 0.95) else _normal_inverse(confidence)
    else:
        critical = 1.959964 if math.isclose(confidence, 0.95) else _normal_inverse(confidence)
    return critical * standard_error


def _normal_inverse(confidence: float) -> float:
    """Two-sided normal critical value for ``confidence`` (e.g. 0.95 -> 1.96).

    Prefers ``scipy.stats.norm.ppf`` (exact). The pure-Python fallback is
    Acklam's full rational approximation including the *tail* refinement —
    the previous code returned a bare ``sqrt(-log(...))`` in the tail, which
    was materially inaccurate for confidence > ~0.85.
    """
    p = 1 - (1 - confidence) / 2
    try:
        from scipy import stats  # type: ignore

        return float(stats.norm.ppf(p))
    except ImportError:  # pragma: no cover - scipy is a hard dependency
        pass

    # Acklam's algorithm (central + tail regions).
    a = [
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577518672690e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    ]
    b = [
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    ]
    c = [
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464968e00,
        2.938163982698783e00,
    ]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00, 3.754408661907416e00]
    p_low = 0.02425
    if p < p_low:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
        )
    if p <= 1 - p_low:
        q = p - 0.5
        r = q * q
        return (
            q
            * (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5])
            / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
        )
    q = math.sqrt(-2 * math.log(1 - p))
    return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
        (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1
    )


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

    rows: list[dict] = []
    for keys, sub in df.groupby(grouping, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        out = dict(zip(grouping, keys, strict=True))
        out["n_seeds"] = len(sub)
        for column in sub.columns:
            if column in grouping or column == "seed":
                continue
            series = sub[column]
            if _is_listy(series):
                # Don't try to dedup or aggregate list-valued cells.
                continue
            # Booleans must not be coerced to 0/1 and averaged: a constant
            # flag like ``n_rounds_is_known`` would otherwise emit a
            # meaningless ``_mean``/``_ci_half_width`` instead of being
            # preserved as the constant it is. Route them through the
            # constant-preservation branch below.
            non_null_vals = series.dropna()
            is_bool = series.dtype == bool or (
                len(non_null_vals) > 0 and all(isinstance(v, bool) for v in non_null_vals)
            )
            numeric = pd.to_numeric(series, errors="coerce")
            if not is_bool and numeric.notna().all():
                values = [float(v) for v in numeric.tolist()]
                mean = sum(values) / len(values)
                out[f"{column}_mean"] = mean
                out[f"{column}_ci_half_width"] = _ci_half_width(values, confidence, use_t=use_t)
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
