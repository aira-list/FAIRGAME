"""Tests for :mod:`src.results_processing.game_metrics`."""

from __future__ import annotations

import unittest

from src.results_processing.game_metrics import (
    equilibrium_metrics,
    gini_coefficient,
    welfare_round_metrics,
    welfare_summary,
)


class TestEquilibriumMetrics(unittest.TestCase):
    def test_rate_when_one_round_in_three_at_equilibrium(self) -> None:
        out = equilibrium_metrics(["c1", "c2", "c4"], equilibria=["c4"])
        self.assertAlmostEqual(out["equilibrium_rate"], 1 / 3)
        self.assertEqual(out["first_equilibrium_round"], 3)
        self.assertEqual(out["equilibrium_per_round"], [False, False, True])

    def test_no_equilibria_yields_no_rate(self) -> None:
        out = equilibrium_metrics([None, None], equilibria=["c4"])
        self.assertIsNone(out["equilibrium_rate"])

    def test_unresolved_rounds_are_none(self) -> None:
        out = equilibrium_metrics(["c1", None, "c4"], equilibria=["c4"])
        self.assertEqual(out["equilibrium_per_round"], [False, None, True])
        self.assertAlmostEqual(out["equilibrium_rate"], 0.5)


class TestWelfare(unittest.TestCase):
    def test_gini_zero_for_equal_distribution(self) -> None:
        self.assertAlmostEqual(gini_coefficient([5, 5, 5]), 0.0)

    def test_gini_positive_for_skewed(self) -> None:
        self.assertGreater(gini_coefficient([0, 0, 10]), 0.5)

    def test_round_metrics(self) -> None:
        out = welfare_round_metrics([1, 2, 3])
        self.assertEqual(out["sum"], 6)
        self.assertEqual(out["min"], 1)
        self.assertEqual(out["max"], 3)
        self.assertAlmostEqual(out["mean"], 2.0)

    def test_summary_efficiency(self) -> None:
        out = welfare_summary({"a": [4, 4], "b": [4, 4]}, pareto_optimal_sum=10)
        # Mean round-sum = 8; pareto optimal sum = 10 -> efficiency 0.8.
        self.assertAlmostEqual(out["welfare_efficiency"], 0.8)
        self.assertAlmostEqual(out["welfare_mean_sum"], 8.0)

    def test_summary_handles_empty(self) -> None:
        out = welfare_summary({})
        self.assertIsNone(out["welfare_mean_sum"])


if __name__ == "__main__":
    unittest.main()
