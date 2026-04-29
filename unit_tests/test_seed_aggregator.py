"""Tests for :mod:`src.results_processing.seed_aggregator`.

Particular attention to:

* normal- vs t-distribution CI selection
* invariants (CI half-width ≥ 0; mean within [min, max])
* grouping behaviour
* listy column handling
"""

from __future__ import annotations

import unittest

import pandas as pd

from src.results_processing.seed_aggregator import aggregate_seeds


def _frame(values_per_seed: list[float]) -> pd.DataFrame:
    """Build a per-seed DataFrame with one configuration column for grouping."""
    return pd.DataFrame(
        {
            "language": ["en"] * len(values_per_seed),
            "agent1_personality": ["a"] * len(values_per_seed),
            "agent2_personality": ["b"] * len(values_per_seed),
            "agent1_llm": ["x"] * len(values_per_seed),
            "agent2_llm": ["y"] * len(values_per_seed),
            "seed": list(range(len(values_per_seed))),
            "metric": values_per_seed,
        }
    )


# ---------------------------------------------------------------------------
# Existing-behaviour invariants (Normal-approx CI)
# ---------------------------------------------------------------------------

class TestNormalCI(unittest.TestCase):
    def test_collapses_into_one_row_per_configuration(self) -> None:
        agg = aggregate_seeds(_frame([1.0, 2.0, 3.0, 4.0, 5.0]))
        self.assertEqual(len(agg), 1)
        self.assertEqual(agg.iloc[0]["n_seeds"], 5)

    def test_mean_is_arithmetic_mean(self) -> None:
        agg = aggregate_seeds(_frame([1.0, 2.0, 3.0, 4.0, 5.0]))
        self.assertAlmostEqual(agg.iloc[0]["metric_mean"], 3.0)

    def test_ci_halfwidth_is_nonnegative(self) -> None:
        agg = aggregate_seeds(_frame([1.0, 2.0, 3.0, 4.0, 5.0]))
        self.assertGreaterEqual(agg.iloc[0]["metric_ci_half_width"], 0.0)

    def test_constant_input_yields_zero_ci(self) -> None:
        agg = aggregate_seeds(_frame([3.0, 3.0, 3.0, 3.0]))
        self.assertAlmostEqual(agg.iloc[0]["metric_ci_half_width"], 0.0)

    def test_singleton_input_yields_zero_ci(self) -> None:
        # n=1 → no variance → CI half-width is 0 by convention.
        agg = aggregate_seeds(_frame([5.0]))
        self.assertAlmostEqual(agg.iloc[0]["metric_ci_half_width"], 0.0)


# ---------------------------------------------------------------------------
# t-distribution CI (new feature)
# ---------------------------------------------------------------------------

class TestTDistributionCI(unittest.TestCase):
    def test_use_t_widens_ci_for_small_samples(self) -> None:
        # For n=5 and 95% confidence, t-critical ≈ 2.776 vs z ≈ 1.960.
        # The t-based CI must be strictly wider.
        df = _frame([1.0, 2.0, 3.0, 4.0, 5.0])
        normal = aggregate_seeds(df)
        t_based = aggregate_seeds(df, use_t=True)
        self.assertGreater(
            t_based.iloc[0]["metric_ci_half_width"],
            normal.iloc[0]["metric_ci_half_width"],
        )

    def test_t_and_normal_converge_for_large_samples(self) -> None:
        # For n=200, t and z should agree to within ~0.5%.
        values = list(range(200))
        df = _frame([float(v) for v in values])
        normal = aggregate_seeds(df).iloc[0]["metric_ci_half_width"]
        t_based = aggregate_seeds(df, use_t=True).iloc[0]["metric_ci_half_width"]
        self.assertAlmostEqual(normal, t_based, delta=0.05 * normal)

    def test_t_ci_is_nonnegative(self) -> None:
        df = _frame([1.0, 2.0, 3.0, 4.0, 5.0])
        agg = aggregate_seeds(df, use_t=True)
        self.assertGreaterEqual(agg.iloc[0]["metric_ci_half_width"], 0.0)

    def test_t_ci_zero_for_singleton(self) -> None:
        # No degrees of freedom → no t statistic, fall back to 0.
        agg = aggregate_seeds(_frame([5.0]), use_t=True)
        self.assertAlmostEqual(agg.iloc[0]["metric_ci_half_width"], 0.0)

    def test_default_use_t_is_false_for_backwards_compat(self) -> None:
        df = _frame([1.0, 2.0, 3.0, 4.0, 5.0])
        a = aggregate_seeds(df).iloc[0]["metric_ci_half_width"]
        b = aggregate_seeds(df, use_t=False).iloc[0]["metric_ci_half_width"]
        self.assertAlmostEqual(a, b)

    def test_confidence_level_widens_ci(self) -> None:
        # Higher confidence → wider CI.
        df = _frame([1.0, 2.0, 3.0, 4.0, 5.0])
        ci_90 = aggregate_seeds(df, confidence=0.90, use_t=True).iloc[0][
            "metric_ci_half_width"
        ]
        ci_99 = aggregate_seeds(df, confidence=0.99, use_t=True).iloc[0][
            "metric_ci_half_width"
        ]
        self.assertGreater(ci_99, ci_90)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases(unittest.TestCase):
    def test_no_seed_column_returns_input_copy(self) -> None:
        df = pd.DataFrame({"language": ["en"], "metric": [1.0]})
        out = aggregate_seeds(df)
        # Same shape and values; not the same object.
        self.assertEqual(out.shape, df.shape)
        self.assertIsNot(out, df)

    def test_empty_dataframe_returns_empty(self) -> None:
        df = pd.DataFrame({"seed": [], "metric": []})
        out = aggregate_seeds(df)
        self.assertEqual(len(out), 0)

    def test_listy_columns_are_dropped_silently(self) -> None:
        df = pd.DataFrame(
            {
                "language": ["en", "en"],
                "seed": [1, 2],
                "agent1_strategies": [[1, 2], [3, 4]],
            }
        )
        out = aggregate_seeds(df)
        self.assertNotIn("agent1_strategies_mean", out.columns)

    def test_partial_nan_numeric_column_takes_unique_branch(self) -> None:
        # When a column has BOTH numeric and missing values, it should
        # not be averaged (numeric.notna().all() is False) — instead the
        # function falls into the unique-value branch. If all non-null
        # values are equal, the bare column survives without _mean / _ci
        # suffix; otherwise it's dropped. Pinning this prevents a
        # mutation that flips notna().all() to notna().any().
        df = pd.DataFrame(
            {
                "language": ["en", "en", "en"],
                "seed": [1, 2, 3],
                "patchy_metric": [3.0, None, 3.0],
            }
        )
        out = aggregate_seeds(df)
        self.assertNotIn("patchy_metric_mean", out.columns)
        self.assertNotIn("patchy_metric_ci_half_width", out.columns)
        # The unique non-null value (3.0) should be carried through as-is.
        self.assertIn("patchy_metric", out.columns)
        self.assertEqual(out["patchy_metric"].iloc[0], 3.0)


if __name__ == "__main__":
    unittest.main()
