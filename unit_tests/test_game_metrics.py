"""Tests for :mod:`src.results_processing.game_metrics`."""

from __future__ import annotations

import unittest

from src.results_processing.game_metrics import (
    equilibrium_metrics,
    gini_coefficient,
    welfare_round_metrics,
    welfare_summary,
)

# ---------------------------------------------------------------------------
# equilibrium_metrics
# ---------------------------------------------------------------------------


class TestEquilibriumMetrics(unittest.TestCase):
    def test_rate_one_in_three(self) -> None:
        out = equilibrium_metrics(["c1", "c2", "c4"], equilibria=["c4"])
        self.assertAlmostEqual(out["equilibrium_rate"], 1 / 3)
        self.assertEqual(out["first_equilibrium_round"], 3)
        self.assertEqual(out["equilibrium_per_round"], [False, False, True])

    def test_all_rounds_at_equilibrium(self) -> None:
        out = equilibrium_metrics(["c4", "c4", "c4"], equilibria=["c4"])
        self.assertAlmostEqual(out["equilibrium_rate"], 1.0)
        self.assertEqual(out["first_equilibrium_round"], 1)
        self.assertEqual(out["equilibrium_per_round"], [True, True, True])

    def test_no_rounds_at_equilibrium(self) -> None:
        out = equilibrium_metrics(["c1", "c2", "c3"], equilibria=["c4"])
        self.assertAlmostEqual(out["equilibrium_rate"], 0.0)
        self.assertIsNone(out["first_equilibrium_round"])
        self.assertEqual(out["equilibrium_per_round"], [False, False, False])

    def test_multiple_equilibria_any_match_counts(self) -> None:
        out = equilibrium_metrics(["c1", "c4", "c2"], equilibria=["c1", "c4"])
        self.assertAlmostEqual(out["equilibrium_rate"], 2 / 3)
        self.assertEqual(out["first_equilibrium_round"], 1)
        self.assertEqual(out["equilibrium_per_round"], [True, True, False])

    def test_all_unresolved_yields_none_rate(self) -> None:
        out = equilibrium_metrics([None, None], equilibria=["c4"])
        self.assertIsNone(out["equilibrium_rate"])
        self.assertIsNone(out["first_equilibrium_round"])

    def test_partial_unresolved_skips_those_rounds_in_rate(self) -> None:
        out = equilibrium_metrics(["c1", None, "c4"], equilibria=["c4"])
        # Only 2 resolved rounds; 1 of them at equilibrium → 0.5.
        self.assertAlmostEqual(out["equilibrium_rate"], 0.5)
        self.assertEqual(out["equilibrium_per_round"], [False, None, True])

    def test_first_equilibrium_round_is_one_indexed(self) -> None:
        out = equilibrium_metrics(["c2", "c4", "c4"], equilibria=["c4"])
        # Round 2 (1-indexed) is the first hit.
        self.assertEqual(out["first_equilibrium_round"], 2)

    def test_empty_input_yields_none_rate(self) -> None:
        out = equilibrium_metrics([], equilibria=["c4"])
        self.assertIsNone(out["equilibrium_rate"])
        self.assertEqual(out["equilibrium_per_round"], [])
        self.assertIsNone(out["first_equilibrium_round"])

    def test_empty_equilibria_means_no_round_qualifies(self) -> None:
        out = equilibrium_metrics(["c1", "c2"], equilibria=[])
        self.assertAlmostEqual(out["equilibrium_rate"], 0.0)
        self.assertEqual(out["equilibrium_per_round"], [False, False])


# ---------------------------------------------------------------------------
# gini_coefficient
# ---------------------------------------------------------------------------


class TestGiniCoefficient(unittest.TestCase):
    def test_zero_for_perfect_equality(self) -> None:
        self.assertAlmostEqual(gini_coefficient([5, 5, 5]), 0.0, places=6)

    def test_positive_for_skewed_distribution(self) -> None:
        self.assertGreater(gini_coefficient([0, 0, 10]), 0.5)

    def test_returns_zero_for_empty_input(self) -> None:
        self.assertEqual(gini_coefficient([]), 0.0)

    def test_singleton_yields_zero(self) -> None:
        # One value = perfect equality (only one slice of the pie).
        self.assertAlmostEqual(gini_coefficient([7]), 0.0)

    def test_strictly_increasing_in_inequality(self) -> None:
        # As the distribution becomes more skewed, Gini grows.
        equal = gini_coefficient([1, 1, 1, 1])
        slight = gini_coefficient([1, 1, 1, 2])
        skewed = gini_coefficient([1, 1, 1, 10])
        self.assertLess(equal, slight)
        self.assertLess(slight, skewed)

    def test_negative_values_are_handled_gracefully(self) -> None:
        # Negative values don't crash; the implementation shifts internally.
        result = gini_coefficient([-1, 0, 1])
        self.assertGreaterEqual(result, 0.0)

    def test_in_unit_interval_for_non_negative_inputs(self) -> None:
        for values in [[1, 2, 3, 4], [0, 0, 0, 5], [10, 10, 10, 10], [0, 100]]:
            g = gini_coefficient(values)
            self.assertGreaterEqual(g, 0.0)
            self.assertLessEqual(g, 1.0)

    def test_invariant_to_uniform_scaling(self) -> None:
        # Multiplying every value by a positive constant doesn't change Gini.
        a = gini_coefficient([1, 2, 3, 4])
        b = gini_coefficient([10, 20, 30, 40])
        self.assertAlmostEqual(a, b, places=6)


# ---------------------------------------------------------------------------
# welfare_round_metrics
# ---------------------------------------------------------------------------


class TestWelfareRoundMetrics(unittest.TestCase):
    def test_basic_round(self) -> None:
        out = welfare_round_metrics([1, 2, 3])
        self.assertEqual(out["sum"], 6)
        self.assertEqual(out["min"], 1)
        self.assertEqual(out["max"], 3)
        self.assertAlmostEqual(out["mean"], 2.0)

    def test_empty_round_returns_zeros(self) -> None:
        out = welfare_round_metrics([])
        self.assertEqual(out["sum"], 0.0)
        self.assertEqual(out["mean"], 0.0)
        self.assertEqual(out["min"], 0.0)
        self.assertEqual(out["max"], 0.0)
        self.assertEqual(out["gini"], 0.0)

    def test_singleton(self) -> None:
        out = welfare_round_metrics([7])
        self.assertEqual(out["sum"], 7)
        self.assertEqual(out["min"], 7)
        self.assertEqual(out["max"], 7)
        self.assertAlmostEqual(out["mean"], 7.0)
        self.assertAlmostEqual(out["gini"], 0.0)

    def test_negative_payoffs(self) -> None:
        out = welfare_round_metrics([-5, 0, 5])
        self.assertEqual(out["sum"], 0)
        self.assertEqual(out["min"], -5)
        self.assertEqual(out["max"], 5)
        self.assertAlmostEqual(out["mean"], 0.0)


# ---------------------------------------------------------------------------
# welfare_summary
# ---------------------------------------------------------------------------


class TestWelfareSummary(unittest.TestCase):
    def test_basic_summary(self) -> None:
        out = welfare_summary({"a": [4, 4], "b": [4, 4]}, pareto_optimal_sum=10)
        self.assertAlmostEqual(out["welfare_mean_sum"], 8.0)
        self.assertAlmostEqual(out["welfare_efficiency"], 0.8)

    def test_efficiency_is_none_without_pareto_sum(self) -> None:
        out = welfare_summary({"a": [4, 4], "b": [4, 4]})
        self.assertIsNone(out["welfare_efficiency"])
        self.assertAlmostEqual(out["welfare_mean_sum"], 8.0)

    def test_efficiency_is_none_when_pareto_zero(self) -> None:
        out = welfare_summary({"a": [4, 4], "b": [4, 4]}, pareto_optimal_sum=0.0)
        self.assertIsNone(out["welfare_efficiency"])

    def test_efficiency_can_exceed_one(self) -> None:
        # If actual welfare > pareto guess, efficiency > 1 (the user gave a
        # bad reference). The function must not clamp.
        out = welfare_summary({"a": [10, 10], "b": [10, 10]}, pareto_optimal_sum=5.0)
        self.assertAlmostEqual(out["welfare_efficiency"], 4.0)

    def test_per_round_list_length_matches_min_rounds(self) -> None:
        out = welfare_summary({"a": [1, 2, 3], "b": [1, 2]})
        # Shorter agent has 2 rounds → output truncates to 2.
        self.assertEqual(len(out["welfare_per_round"]), 2)

    def test_empty_input_returns_none_means(self) -> None:
        out = welfare_summary({})
        self.assertIsNone(out["welfare_mean_sum"])
        self.assertIsNone(out["welfare_mean_min"])
        self.assertIsNone(out["welfare_mean_gini"])
        self.assertIsNone(out["welfare_efficiency"])
        self.assertEqual(out["welfare_per_round"], [])

    def test_all_agents_have_zero_rounds(self) -> None:
        out = welfare_summary({"a": [], "b": []})
        self.assertIsNone(out["welfare_mean_sum"])

    def test_invariant_min_le_mean_le_max(self) -> None:
        # Per round, the welfare metrics should satisfy min ≤ mean ≤ max.
        out = welfare_summary({"a": [1, 5], "b": [3, 5]})
        for round_metrics in out["welfare_per_round"]:
            self.assertLessEqual(round_metrics["min"], round_metrics["mean"])
            self.assertLessEqual(round_metrics["mean"], round_metrics["max"])


if __name__ == "__main__":
    unittest.main()
