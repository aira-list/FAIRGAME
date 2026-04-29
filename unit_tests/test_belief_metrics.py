"""Tests for :mod:`src.results_processing.belief_metrics`."""

from __future__ import annotations

import unittest

from src.results_processing.belief_metrics import (
    aggregate_metrics,
    belief_agreement,
    brier_score,
    per_round_metrics,
)


class TestBeliefMetrics(unittest.TestCase):
    def test_brier_perfect_forecast_is_zero(self) -> None:
        belief = {"strategy1": 1.0, "strategy2": 0.0}
        self.assertEqual(brier_score(belief, "strategy1"), 0.0)

    def test_brier_uniform_forecast_is_half(self) -> None:
        belief = {"strategy1": 0.5, "strategy2": 0.5}
        self.assertAlmostEqual(brier_score(belief, "strategy1"), 0.5)

    def test_brier_completely_wrong_is_two(self) -> None:
        belief = {"strategy1": 0.0, "strategy2": 1.0}
        self.assertAlmostEqual(brier_score(belief, "strategy1"), 2.0)

    def test_belief_agreement_picks_modal(self) -> None:
        belief = {"strategy1": 0.7, "strategy2": 0.3}
        self.assertTrue(belief_agreement(belief, "strategy1"))
        self.assertFalse(belief_agreement(belief, "strategy2"))

    def test_per_round_metrics_handles_missing(self) -> None:
        beliefs = [{"strategy1": 0.6, "strategy2": 0.4}, None, {"strategy1": 1.0}]
        opponents = ["strategy1", "strategy2", None]
        result = per_round_metrics(beliefs, opponents)
        self.assertIsNotNone(result[0])
        self.assertIsNone(result[1])
        self.assertIsNone(result[2])
        self.assertAlmostEqual(result[0]["p_outcome"], 0.6)

    def test_aggregate_metrics_averages_only_valid_rounds(self) -> None:
        per_round = [
            {"brier": 0.0, "p_outcome": 1.0, "agreement": 1.0},
            {"brier": 0.5, "p_outcome": 0.5, "agreement": 0.0},
            None,
        ]
        agg = aggregate_metrics(per_round)
        self.assertAlmostEqual(agg["mean_brier"], 0.25)
        self.assertAlmostEqual(agg["mean_p_outcome"], 0.75)
        self.assertAlmostEqual(agg["agreement_rate"], 0.5)

    def test_aggregate_metrics_all_missing(self) -> None:
        agg = aggregate_metrics([None, None])
        self.assertEqual(agg, {"mean_brier": None, "mean_p_outcome": None, "agreement_rate": None})


if __name__ == "__main__":
    unittest.main()
