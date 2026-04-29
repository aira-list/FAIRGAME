"""Tests for :mod:`src.results_processing.stats`."""

from __future__ import annotations

import unittest

import pandas as pd

from src.results_processing.stats import (
    compare_metric,
    compare_metrics,
    default_comparison_metrics,
    extract_numeric,
)


class TestExtractNumeric(unittest.TestCase):
    def test_drops_nans_and_strings(self) -> None:
        df = pd.DataFrame({"x": [1, 2, "bad", None, 3.5]})
        self.assertEqual(extract_numeric(df, "x"), [1.0, 2.0, 3.5])

    def test_returns_empty_for_missing_column(self) -> None:
        self.assertEqual(extract_numeric(pd.DataFrame(), "x"), [])


class TestCompareMetric(unittest.TestCase):
    def test_distinct_distributions_have_low_pvalue(self) -> None:
        df_a = pd.DataFrame({"x": [10, 11, 12, 13, 14]})
        df_b = pd.DataFrame({"x": [1, 2, 3, 4, 5]})
        result = compare_metric(df_a, df_b, "x")
        self.assertEqual(result.metric, "x")
        self.assertEqual(result.n_a, 5)
        self.assertEqual(result.n_b, 5)
        self.assertAlmostEqual(result.mean_a, 12.0)
        self.assertAlmostEqual(result.mean_b, 3.0)
        self.assertAlmostEqual(result.mean_diff, 9.0)
        self.assertIsNotNone(result.welch_p)
        self.assertLess(result.welch_p, 0.01)
        self.assertIsNotNone(result.mannwhitney_p)
        self.assertLess(result.mannwhitney_p, 0.05)

    def test_identical_distributions_have_high_pvalue(self) -> None:
        df_a = pd.DataFrame({"x": [5, 6, 7, 8, 9]})
        df_b = pd.DataFrame({"x": [5, 6, 7, 8, 9]})
        result = compare_metric(df_a, df_b, "x")
        self.assertAlmostEqual(result.mean_diff, 0.0)
        self.assertGreater(result.welch_p or 0.0, 0.5)

    def test_empty_a_returns_nan_means(self) -> None:
        result = compare_metric(pd.DataFrame({"x": []}), pd.DataFrame({"x": [1, 2]}), "x")
        self.assertEqual(result.n_a, 0)
        self.assertNotEqual(result.mean_a, result.mean_a)  # NaN check


class TestCompareMetricsSweep(unittest.TestCase):
    def test_returns_one_row_per_metric(self) -> None:
        df_a = pd.DataFrame({"x": [1, 2, 3], "y": [10, 20, 30]})
        df_b = pd.DataFrame({"x": [4, 5, 6], "y": [10, 20, 30]})
        out = compare_metrics(df_a, df_b, ["x", "y"])
        self.assertEqual(len(out), 2)
        self.assertEqual(set(out["metric"]), {"x", "y"})


class TestDefaultComparisonMetrics(unittest.TestCase):
    def test_returns_only_columns_that_exist(self) -> None:
        df = pd.DataFrame({"welfare_mean_sum": [1], "equilibrium_rate": [0.5]})
        result = default_comparison_metrics(df)
        self.assertIn("welfare_mean_sum", result)
        self.assertIn("equilibrium_rate", result)
        self.assertNotIn("agent1_belief_mean_brier", result)


if __name__ == "__main__":
    unittest.main()
