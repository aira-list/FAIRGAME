"""Tests for :mod:`src.results_processing.belief_metrics`."""

from __future__ import annotations

import unittest

from src.results_processing.belief_metrics import (
    aggregate_metrics,
    belief_agreement,
    brier_score,
    per_round_metrics,
)


# ---------------------------------------------------------------------------
# brier_score
# ---------------------------------------------------------------------------

class TestBrierScore(unittest.TestCase):
    def test_perfect_forecast_is_zero(self) -> None:
        self.assertEqual(brier_score({"a": 1.0, "b": 0.0}, "a"), 0.0)

    def test_uniform_two_class_is_half(self) -> None:
        self.assertAlmostEqual(brier_score({"a": 0.5, "b": 0.5}, "a"), 0.5)

    def test_completely_wrong_is_two(self) -> None:
        # All mass on the wrong class → (0-1)^2 + (1-0)^2 = 2.
        self.assertAlmostEqual(brier_score({"a": 0.0, "b": 1.0}, "a"), 2.0)

    def test_score_is_nonnegative(self) -> None:
        beliefs = [
            {"a": 0.1, "b": 0.9},
            {"a": 1.0, "b": 0.0},
            {"a": 0.5, "b": 0.5},
        ]
        for belief in beliefs:
            self.assertGreaterEqual(brier_score(belief, "a"), 0.0)
            self.assertGreaterEqual(brier_score(belief, "b"), 0.0)

    def test_score_is_at_most_two_for_binary_belief(self) -> None:
        # Within the proper-scoring-rule regime, multi-class Brier is in [0, 2]
        # whenever the forecast is a probability vector.
        for p in [0.0, 0.1, 0.5, 0.9, 1.0]:
            score = brier_score({"a": p, "b": 1 - p}, "a")
            self.assertLessEqual(score, 2.0)

    def test_three_class_uniform_forecast(self) -> None:
        # Three classes, uniform: each off-class contributes (1/3)^2 and the
        # right class contributes (2/3)^2 → total 6/9 = 2/3.
        belief = {"a": 1 / 3, "b": 1 / 3, "c": 1 / 3}
        self.assertAlmostEqual(brier_score(belief, "a"), 2 / 3, places=6)

    def test_empty_belief_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            brier_score({}, "a")


# ---------------------------------------------------------------------------
# belief_agreement
# ---------------------------------------------------------------------------

class TestBeliefAgreement(unittest.TestCase):
    def test_picks_modal_strategy(self) -> None:
        belief = {"a": 0.7, "b": 0.3}
        self.assertTrue(belief_agreement(belief, "a"))
        self.assertFalse(belief_agreement(belief, "b"))

    def test_three_class_picks_largest(self) -> None:
        belief = {"a": 0.2, "b": 0.5, "c": 0.3}
        self.assertTrue(belief_agreement(belief, "b"))
        self.assertFalse(belief_agreement(belief, "a"))
        self.assertFalse(belief_agreement(belief, "c"))

    def test_empty_belief_returns_false(self) -> None:
        # No prediction can be "right" without a belief.
        self.assertFalse(belief_agreement({}, "a"))

    def test_ties_pick_a_deterministic_winner(self) -> None:
        # Ties resolve by Python max iteration order — the assertion is
        # only that the function is *deterministic* and returns a boolean.
        belief = {"a": 0.5, "b": 0.5}
        result = belief_agreement(belief, "a")
        self.assertIsInstance(result, bool)
        # Same input must produce the same output.
        self.assertEqual(result, belief_agreement({"a": 0.5, "b": 0.5}, "a"))


# ---------------------------------------------------------------------------
# per_round_metrics
# ---------------------------------------------------------------------------

class TestPerRoundMetrics(unittest.TestCase):
    def test_complete_data_yields_dicts(self) -> None:
        beliefs = [{"a": 0.6, "b": 0.4}]
        result = per_round_metrics(beliefs, ["a"])
        self.assertEqual(len(result), 1)
        self.assertIsNotNone(result[0])
        self.assertAlmostEqual(result[0]["p_outcome"], 0.6)

    def test_missing_belief_yields_none(self) -> None:
        result = per_round_metrics([None], ["a"])
        self.assertEqual(result, [None])

    def test_empty_belief_yields_none(self) -> None:
        result = per_round_metrics([{}], ["a"])
        self.assertEqual(result, [None])

    def test_missing_outcome_yields_none(self) -> None:
        result = per_round_metrics([{"a": 0.6, "b": 0.4}], [None])
        self.assertEqual(result, [None])

    def test_mixed_valid_and_missing_rounds(self) -> None:
        beliefs = [{"a": 0.6, "b": 0.4}, None, {"a": 1.0}]
        opponents = ["a", "b", None]
        result = per_round_metrics(beliefs, opponents)
        self.assertIsNotNone(result[0])
        self.assertIsNone(result[1])
        self.assertIsNone(result[2])
        self.assertAlmostEqual(result[0]["p_outcome"], 0.6)

    def test_output_length_matches_input(self) -> None:
        # Whether or not a round resolves, the result list must have the
        # same length as the inputs (caller iterates positionally).
        beliefs = [None, {"a": 1.0}, None, {"a": 0.5, "b": 0.5}]
        outcomes = ["a", "a", None, "b"]
        result = per_round_metrics(beliefs, outcomes)
        self.assertEqual(len(result), len(beliefs))

    def test_p_outcome_always_in_unit_interval(self) -> None:
        # Whatever the belief, p_outcome must lie in [0, 1].
        beliefs = [
            {"a": 0.0, "b": 1.0},
            {"a": 0.5, "b": 0.5},
            {"a": 1.0, "b": 0.0},
        ]
        outcomes = ["a", "a", "a"]
        for m in per_round_metrics(beliefs, outcomes):
            self.assertIsNotNone(m)
            self.assertGreaterEqual(m["p_outcome"], 0.0)
            self.assertLessEqual(m["p_outcome"], 1.0)

    def test_brier_within_zero_two(self) -> None:
        beliefs = [{"a": 0.0, "b": 1.0}, {"a": 1.0, "b": 0.0}]
        outcomes = ["a", "b"]
        for m in per_round_metrics(beliefs, outcomes):
            self.assertIsNotNone(m)
            self.assertGreaterEqual(m["brier"], 0.0)
            self.assertLessEqual(m["brier"], 2.0)


# ---------------------------------------------------------------------------
# aggregate_metrics
# ---------------------------------------------------------------------------

class TestAggregateMetrics(unittest.TestCase):
    def test_averages_only_valid_rounds(self) -> None:
        per_round = [
            {"brier": 0.0, "p_outcome": 1.0, "agreement": 1.0},
            {"brier": 0.5, "p_outcome": 0.5, "agreement": 0.0},
            None,
        ]
        agg = aggregate_metrics(per_round)
        self.assertAlmostEqual(agg["mean_brier"], 0.25)
        self.assertAlmostEqual(agg["mean_p_outcome"], 0.75)
        self.assertAlmostEqual(agg["agreement_rate"], 0.5)

    def test_all_missing_yields_none_means(self) -> None:
        self.assertEqual(
            aggregate_metrics([None, None]),
            {"mean_brier": None, "mean_p_outcome": None, "agreement_rate": None},
        )

    def test_empty_input_yields_none_means(self) -> None:
        self.assertEqual(
            aggregate_metrics([]),
            {"mean_brier": None, "mean_p_outcome": None, "agreement_rate": None},
        )

    def test_single_round_aggregate_equals_that_round(self) -> None:
        per_round = [{"brier": 0.4, "p_outcome": 0.6, "agreement": 1.0}]
        agg = aggregate_metrics(per_round)
        self.assertAlmostEqual(agg["mean_brier"], 0.4)
        self.assertAlmostEqual(agg["mean_p_outcome"], 0.6)
        self.assertAlmostEqual(agg["agreement_rate"], 1.0)

    def test_invariant_means_in_expected_ranges(self) -> None:
        # mean_brier ∈ [0, 2]; mean_p_outcome ∈ [0, 1]; agreement_rate ∈ [0, 1].
        per_round = [
            {"brier": 0.0, "p_outcome": 1.0, "agreement": 1.0},
            {"brier": 2.0, "p_outcome": 0.0, "agreement": 0.0},
        ]
        agg = aggregate_metrics(per_round)
        self.assertGreaterEqual(agg["mean_brier"], 0.0)
        self.assertLessEqual(agg["mean_brier"], 2.0)
        self.assertGreaterEqual(agg["mean_p_outcome"], 0.0)
        self.assertLessEqual(agg["mean_p_outcome"], 1.0)
        self.assertGreaterEqual(agg["agreement_rate"], 0.0)
        self.assertLessEqual(agg["agreement_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
