"""Tests for :mod:`src.results_processing.stats`.

Behaviour-level tests of the hypothesis-testing helpers. Each test
exercises one narrow contract; edge-case inputs (singletons, NaN-only,
zero-variance, missing column) get their own cases.
"""

from __future__ import annotations

import math
import unittest

import pandas as pd

from src.results_processing.stats import (
    ComparisonResult,
    compare_metric,
    compare_metrics,
    default_comparison_metrics,
    extract_numeric,
)

# ---------------------------------------------------------------------------
# extract_numeric
# ---------------------------------------------------------------------------


class TestExtractNumeric(unittest.TestCase):
    def test_drops_strings_and_nans(self) -> None:
        df = pd.DataFrame({"x": [1, 2, "bad", None, 3.5]})
        self.assertEqual(extract_numeric(df, "x"), [1.0, 2.0, 3.5])

    def test_returns_empty_for_missing_column(self) -> None:
        self.assertEqual(extract_numeric(pd.DataFrame(), "x"), [])

    def test_returns_empty_for_all_nan_column(self) -> None:
        df = pd.DataFrame({"x": [None, None, None]})
        self.assertEqual(extract_numeric(df, "x"), [])

    def test_does_not_mutate_input_dataframe(self) -> None:
        df = pd.DataFrame({"x": [1, 2, "bad", None, 3.5]})
        snapshot = df.copy()
        _ = extract_numeric(df, "x")
        pd.testing.assert_frame_equal(df, snapshot)

    def test_preserves_order(self) -> None:
        df = pd.DataFrame({"x": [3.0, 1.0, 2.0]})
        self.assertEqual(extract_numeric(df, "x"), [3.0, 1.0, 2.0])


# ---------------------------------------------------------------------------
# compare_metric: happy paths
# ---------------------------------------------------------------------------


class TestCompareMetricHappyPath(unittest.TestCase):
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
        same = [5, 6, 7, 8, 9]
        result = compare_metric(pd.DataFrame({"x": same}), pd.DataFrame({"x": same}), "x")
        self.assertAlmostEqual(result.mean_diff, 0.0)
        self.assertGreater(result.welch_p or 0.0, 0.5)

    def test_mean_diff_sign_follows_argument_order(self) -> None:
        df_a = pd.DataFrame({"x": [5, 6, 7]})
        df_b = pd.DataFrame({"x": [1, 2, 3]})
        forward = compare_metric(df_a, df_b, "x")
        backward = compare_metric(df_b, df_a, "x")
        self.assertAlmostEqual(forward.mean_diff, -backward.mean_diff)

    def test_welch_t_sign_matches_mean_diff(self) -> None:
        df_a = pd.DataFrame({"x": [10, 11, 12]})
        df_b = pd.DataFrame({"x": [1, 2, 3]})
        result = compare_metric(df_a, df_b, "x")
        self.assertGreater(result.welch_t, 0)  # mean_a > mean_b

    def test_n_a_and_n_b_count_only_numeric_rows(self) -> None:
        df_a = pd.DataFrame({"x": [1, "bad", 2, None, 3]})
        df_b = pd.DataFrame({"x": [4, 5, 6]})
        result = compare_metric(df_a, df_b, "x")
        self.assertEqual(result.n_a, 3)
        self.assertEqual(result.n_b, 3)


# ---------------------------------------------------------------------------
# compare_metric: edge cases
# ---------------------------------------------------------------------------


class TestCompareMetricEdgeCases(unittest.TestCase):
    def test_empty_a_yields_nan_mean_a(self) -> None:
        result = compare_metric(pd.DataFrame({"x": []}), pd.DataFrame({"x": [1, 2]}), "x")
        self.assertEqual(result.n_a, 0)
        self.assertTrue(math.isnan(result.mean_a))
        # Tests can't run with an empty sample → both p-values are None.
        self.assertIsNone(result.welch_p)
        self.assertIsNone(result.mannwhitney_p)

    def test_both_empty_yields_nan_means(self) -> None:
        result = compare_metric(pd.DataFrame({"x": []}), pd.DataFrame({"x": []}), "x")
        self.assertEqual(result.n_a, 0)
        self.assertEqual(result.n_b, 0)
        self.assertTrue(math.isnan(result.mean_a))
        self.assertTrue(math.isnan(result.mean_b))
        self.assertTrue(math.isnan(result.mean_diff))

    def test_singleton_samples_dont_crash(self) -> None:
        # n=1 has zero variance → Welch may return nan or fail; we accept
        # either as long as the call itself doesn't raise.
        result = compare_metric(pd.DataFrame({"x": [1]}), pd.DataFrame({"x": [10]}), "x")
        self.assertEqual(result.n_a, 1)
        self.assertEqual(result.n_b, 1)
        self.assertAlmostEqual(result.mean_diff, -9.0)

    def test_zero_variance_in_both_samples(self) -> None:
        # Identical constant samples → no test statistic possible; mean_diff
        # must still be 0 and the call must not raise.
        result = compare_metric(pd.DataFrame({"x": [5, 5, 5]}), pd.DataFrame({"x": [5, 5, 5]}), "x")
        self.assertAlmostEqual(result.mean_diff, 0.0)

    def test_missing_column_yields_zero_n(self) -> None:
        result = compare_metric(pd.DataFrame({"y": [1, 2]}), pd.DataFrame({"x": [3]}), "x")
        self.assertEqual(result.n_a, 0)
        self.assertEqual(result.n_b, 1)


# ---------------------------------------------------------------------------
# ComparisonResult dataclass
# ---------------------------------------------------------------------------


class TestComparisonResultDataclass(unittest.TestCase):
    def test_to_dict_round_trip_keys(self) -> None:
        result = compare_metric(pd.DataFrame({"x": [1, 2]}), pd.DataFrame({"x": [3, 4]}), "x")
        d = result.to_dict()
        # All declared fields appear.
        for field in (
            "metric",
            "n_a",
            "n_b",
            "mean_a",
            "mean_b",
            "mean_diff",
            "welch_t",
            "welch_p",
            "mannwhitney_u",
            "mannwhitney_p",
        ):
            self.assertIn(field, d)

    def test_dataclass_can_be_reconstructed_from_dict(self) -> None:
        result = compare_metric(pd.DataFrame({"x": [1, 2]}), pd.DataFrame({"x": [3, 4]}), "x")
        d = result.to_dict()
        rebuilt = ComparisonResult(**d)
        self.assertEqual(rebuilt.to_dict(), d)


# ---------------------------------------------------------------------------
# compare_metrics (sweep)
# ---------------------------------------------------------------------------


class TestCompareMetricsSweep(unittest.TestCase):
    def test_one_row_per_metric(self) -> None:
        df_a = pd.DataFrame({"x": [1, 2, 3], "y": [10, 20, 30]})
        df_b = pd.DataFrame({"x": [4, 5, 6], "y": [10, 20, 30]})
        out = compare_metrics(df_a, df_b, ["x", "y"])
        self.assertEqual(len(out), 2)
        self.assertEqual(set(out["metric"]), {"x", "y"})

    def test_empty_metric_list_yields_empty_dataframe(self) -> None:
        df_a = pd.DataFrame({"x": [1]})
        df_b = pd.DataFrame({"x": [2]})
        out = compare_metrics(df_a, df_b, [])
        self.assertEqual(len(out), 0)

    def test_metric_missing_from_both_yields_zero_counts(self) -> None:
        df_a = pd.DataFrame({"x": [1]})
        df_b = pd.DataFrame({"x": [2]})
        out = compare_metrics(df_a, df_b, ["does_not_exist"])
        row = out.iloc[0]
        self.assertEqual(row["n_a"], 0)
        self.assertEqual(row["n_b"], 0)


# ---------------------------------------------------------------------------
# default_comparison_metrics
# ---------------------------------------------------------------------------


class TestMultipleComparisonCorrection(unittest.TestCase):
    """``compare_metrics`` must support Bonferroni and Holm corrections so
    multi-metric exploratory comparisons don't produce inflated false
    positives."""

    def _three_metric_inputs(self) -> tuple:
        # Three metrics, each with the same A/B distinction.
        df_a = pd.DataFrame({"x": [10, 11, 12, 13], "y": [10, 11, 12, 13], "z": [10, 11, 12, 13]})
        df_b = pd.DataFrame({"x": [1, 2, 3, 4], "y": [1, 2, 3, 4], "z": [1, 2, 3, 4]})
        return df_a, df_b

    def test_bonferroni_multiplies_pvalues_by_count(self) -> None:
        df_a, df_b = self._three_metric_inputs()
        out_raw = compare_metrics(df_a, df_b, ["x", "y", "z"], correction="none")
        out_bon = compare_metrics(df_a, df_b, ["x", "y", "z"], correction="bonferroni")
        # Each Bonferroni-adjusted p must be 3x the raw p (capped at 1.0).
        for raw, bon in zip(out_raw["welch_p"], out_bon["welch_p_adjusted"], strict=True):
            self.assertAlmostEqual(min(raw * 3, 1.0), bon, places=6)

    def test_holm_is_at_least_as_strict_as_raw_but_no_worse_than_bonferroni(self) -> None:
        df_a, df_b = self._three_metric_inputs()
        out_raw = compare_metrics(df_a, df_b, ["x", "y", "z"], correction="none")
        out_holm = compare_metrics(df_a, df_b, ["x", "y", "z"], correction="holm")
        out_bon = compare_metrics(df_a, df_b, ["x", "y", "z"], correction="bonferroni")
        for raw, holm, bon in zip(
            out_raw["welch_p"],
            out_holm["welch_p_adjusted"],
            out_bon["welch_p_adjusted"],
            strict=True,
        ):
            self.assertGreaterEqual(holm, raw - 1e-9)
            self.assertLessEqual(holm, bon + 1e-9)

    def test_correction_none_passes_pvalues_through_unchanged(self) -> None:
        df_a, df_b = self._three_metric_inputs()
        out_raw = compare_metrics(df_a, df_b, ["x", "y", "z"], correction="none")
        # The adjusted column equals the raw p.
        for raw, adj in zip(out_raw["welch_p"], out_raw["welch_p_adjusted"], strict=True):
            self.assertAlmostEqual(raw, adj)

    def test_unknown_correction_method_rejected(self) -> None:
        df_a, df_b = self._three_metric_inputs()
        with self.assertRaises(ValueError):
            compare_metrics(df_a, df_b, ["x"], correction="bogus")

    def test_default_correction_is_none(self) -> None:
        # Backward-compat: existing callers without the kwarg get raw p-values.
        df_a, df_b = self._three_metric_inputs()
        out_default = compare_metrics(df_a, df_b, ["x"])
        out_explicit = compare_metrics(df_a, df_b, ["x"], correction="none")
        # Same adjusted values.
        self.assertAlmostEqual(
            out_default["welch_p_adjusted"].iloc[0],
            out_explicit["welch_p_adjusted"].iloc[0],
        )

    def test_correction_applies_to_mannwhitney_too(self) -> None:
        df_a, df_b = self._three_metric_inputs()
        out_bon = compare_metrics(df_a, df_b, ["x", "y", "z"], correction="bonferroni")
        self.assertIn("mannwhitney_p_adjusted", out_bon.columns)


class TestStatsMutmutCoverage(unittest.TestCase):
    """Targeted coverage for behaviours mutmut found unexercised."""

    @staticmethod
    def _heterogeneous_inputs() -> tuple:
        # Three metrics with a deliberately wide spread of effect sizes,
        # so Bonferroni and Holm produce different adjusted p-values.
        df_a = pd.DataFrame(
            {
                # Big effect → tiny raw p.
                "strong": [10, 11, 12, 13, 14, 15, 16, 17],
                # Small effect → moderate raw p.
                "mild": [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7],
                # No effect → near-1.0 raw p.
                "null": [5, 5, 5, 5, 5, 5, 5, 5],
            }
        )
        df_b = pd.DataFrame(
            {
                "strong": [1, 2, 3, 4, 5, 6, 7, 8],
                "mild": [1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.7, 1.8],
                "null": [5, 5, 5, 5, 5, 5, 5, 5],
            }
        )
        return df_a, df_b

    def test_mannwhitney_statistic_is_finite_for_normal_inputs(self) -> None:
        # The U statistic must be a real number, not None — assigning
        # the float() cast keeps regressions from silently dropping it.
        df_a = pd.DataFrame({"x": [1, 2, 3, 4, 5, 6, 7, 8]})
        df_b = pd.DataFrame({"x": [10, 11, 12, 13, 14, 15, 16, 17]})
        result = compare_metric(df_a, df_b, "x")
        self.assertIsNotNone(result.mannwhitney_u)
        self.assertIsNotNone(result.mannwhitney_p)

    def test_mannwhitney_p_adjusted_is_filled_in(self) -> None:
        # mannwhitney_p_adjusted must carry the corrected p — never None
        # for inputs whose raw mannwhitney_p is itself a real number.
        df_a, df_b = self._heterogeneous_inputs()
        out = compare_metrics(df_a, df_b, ["strong", "mild"], correction="bonferroni")
        for adj in out["mannwhitney_p_adjusted"]:
            self.assertIsNotNone(adj)

    def test_correction_column_carries_method_name(self) -> None:
        df_a, df_b = self._heterogeneous_inputs()
        for method in ("none", "bonferroni", "holm"):
            out = compare_metrics(df_a, df_b, ["strong", "mild", "null"], correction=method)
            self.assertIn("correction", out.columns)
            for value in out["correction"]:
                self.assertEqual(value, method)

    def test_holm_diverges_from_bonferroni_for_heterogeneous_pvalues(self) -> None:
        # Direct unit test of the adjustment helper, bypassing the
        # Welch-noise sensitivity that makes constructing precise
        # raw p-values from DataFrames brittle.
        #
        # With raw = [0.001, 0.1, 0.3] (n=3):
        #   Bonferroni: [0.003, 0.3, 0.9]
        #   Holm:       [0.003, 0.2, 0.3]
        # The two methods diverge wherever a p is not the smallest in
        # its set — that's the whole point of step-down vs step-uniform.
        from src.results_processing.stats import _adjust_pvalues

        raw = [0.001, 0.1, 0.3]
        bon = _adjust_pvalues(raw, "bonferroni")
        holm = _adjust_pvalues(raw, "holm")
        # Smallest p gets multiplied by n in both methods → identical.
        self.assertAlmostEqual(bon[0], holm[0], places=9)
        # Middle and largest must be strictly smaller under Holm.
        self.assertLess(holm[1], bon[1] - 1e-9)
        self.assertLess(holm[2], bon[2] - 1e-9)
        # Sanity: holm preserves the input order (i.e. is not sorted).
        self.assertAlmostEqual(holm[0], 0.003, places=9)
        self.assertAlmostEqual(holm[1], 0.2, places=9)
        self.assertAlmostEqual(holm[2], 0.3, places=9)

    def test_holm_recovers_input_order_after_internal_sort(self) -> None:
        # If Holm sorted by index instead of by p (or skipped sorting
        # entirely), the largest of the three raw inputs would land in
        # position 0 of the adjusted output. Pinning the position of
        # each adjusted value catches that mutation.
        from src.results_processing.stats import _adjust_pvalues

        raw = [0.3, 0.001, 0.1]  # raw[0] is largest; raw[1] is smallest
        holm = _adjust_pvalues(raw, "holm")
        # Position 1 (smallest raw) gets multiplied by n=3 → 0.003.
        self.assertAlmostEqual(holm[1], 0.003, places=9)
        # Position 2 gets the n-1=2 multiplier → 0.2.
        self.assertAlmostEqual(holm[2], 0.2, places=9)
        # Position 0 (largest raw) gets the n-2=1 multiplier → 0.3.
        self.assertAlmostEqual(holm[0], 0.3, places=9)

    def test_bonferroni_caps_at_one_not_an_arbitrary_higher_value(self) -> None:
        # When raw_p * n exceeds 1.0, the adjusted value must clamp to
        # exactly 1.0 — not 2.0 or any other ceiling. Direct call
        # bypasses the Welch numerical-edge-case noise that turns the
        # raw p into NaN when both samples are degenerate.
        from src.results_processing.stats import _adjust_pvalues

        # Bonferroni: 0.5 * 3 = 1.5 → must cap to 1.0.
        bon = _adjust_pvalues([0.5, 0.5, 0.5], "bonferroni")
        for adj in bon:
            self.assertEqual(adj, 1.0)

        # Holm: largest at running_max = 0.5 * 3 = 1.5 → cap to 1.0.
        holm = _adjust_pvalues([0.5, 0.5, 0.5], "holm")
        for adj in holm:
            self.assertEqual(adj, 1.0)


class TestDefaultComparisonMetrics(unittest.TestCase):
    def test_returns_only_existing_columns(self) -> None:
        df = pd.DataFrame({"welfare_mean_sum": [1], "equilibrium_rate": [0.5]})
        result = default_comparison_metrics(df)
        self.assertIn("welfare_mean_sum", result)
        self.assertIn("equilibrium_rate", result)
        self.assertNotIn("agent1_belief_mean_brier", result)

    def test_returns_empty_when_no_known_metrics_present(self) -> None:
        df = pd.DataFrame({"unrelated": [1, 2]})
        self.assertEqual(default_comparison_metrics(df), [])

    def test_includes_regret_columns_when_present(self) -> None:
        df = pd.DataFrame({"agent1_regret_mean": [0.1], "agent2_regret_mean": [0.2]})
        result = default_comparison_metrics(df)
        self.assertIn("agent1_regret_mean", result)
        self.assertIn("agent2_regret_mean", result)


if __name__ == "__main__":
    unittest.main()
