"""Tests for :mod:`src.belief_parser`."""

from __future__ import annotations

import unittest

from src.belief_parser import BeliefParseError, parse_belief

STRATEGIES = {"strategy1": "Cooperate", "strategy2": "Defect"}
THREE_STRATEGIES = {
    "strategy1": "Rock",
    "strategy2": "Paper",
    "strategy3": "Scissors",
}


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


class TestHappyPath(unittest.TestCase):
    def test_parses_clean_json_with_display_labels(self) -> None:
        result = parse_belief('{"Cooperate": 0.7, "Defect": 0.3}', STRATEGIES)
        self.assertAlmostEqual(result["strategy1"], 0.7)
        self.assertAlmostEqual(result["strategy2"], 0.3)

    def test_parses_canonical_keys(self) -> None:
        result = parse_belief('{"strategy1": 0.6, "strategy2": 0.4}', STRATEGIES)
        self.assertAlmostEqual(result["strategy1"], 0.6)
        self.assertAlmostEqual(result["strategy2"], 0.4)

    def test_mixes_keys_and_labels(self) -> None:
        # Some LLMs use the canonical key for one strategy and the display
        # label for another.
        result = parse_belief('{"strategy1": 0.6, "Defect": 0.4}', STRATEGIES)
        self.assertAlmostEqual(result["strategy1"], 0.6)
        self.assertAlmostEqual(result["strategy2"], 0.4)

    def test_label_match_is_case_insensitive(self) -> None:
        # Display labels should match regardless of case (LLMs vary).
        result = parse_belief('{"COOPERATE": 0.4, "defect": 0.6}', STRATEGIES)
        self.assertAlmostEqual(result["strategy1"], 0.4)
        self.assertAlmostEqual(result["strategy2"], 0.6)

    def test_three_strategy_distribution(self) -> None:
        text = '{"Rock": 0.2, "Paper": 0.3, "Scissors": 0.5}'
        result = parse_belief(text, THREE_STRATEGIES)
        self.assertAlmostEqual(result["strategy1"], 0.2)
        self.assertAlmostEqual(result["strategy2"], 0.3)
        self.assertAlmostEqual(result["strategy3"], 0.5)


# ---------------------------------------------------------------------------
# Robust-extraction (prose around the JSON)
# ---------------------------------------------------------------------------


class TestProseExtraction(unittest.TestCase):
    def test_extracts_from_prefix_prose(self) -> None:
        text = 'Sure! Here is my belief: {"Cooperate": 0.5, "Defect": 0.5}'
        result = parse_belief(text, STRATEGIES)
        self.assertAlmostEqual(result["strategy1"], 0.5)

    def test_extracts_from_suffix_prose(self) -> None:
        text = '{"Cooperate": 0.5, "Defect": 0.5}. Hope this is helpful.'
        result = parse_belief(text, STRATEGIES)
        self.assertAlmostEqual(result["strategy1"], 0.5)

    def test_handles_stray_brace_after_json(self) -> None:
        # Brace-balanced extraction must NOT be confused by a later } in prose.
        text = '{"Cooperate": 0.5, "Defect": 0.5}. End of message } actually.'
        result = parse_belief(text, STRATEGIES)
        self.assertAlmostEqual(result["strategy1"], 0.5)

    def test_handles_newlines_inside_json(self) -> None:
        text = '{\n  "Cooperate": 0.7,\n  "Defect": 0.3\n}'
        result = parse_belief(text, STRATEGIES)
        self.assertAlmostEqual(result["strategy1"], 0.7)


# ---------------------------------------------------------------------------
# Renormalisation
# ---------------------------------------------------------------------------


class TestRenormalisation(unittest.TestCase):
    def test_sum_within_tolerance_is_renormalised_to_one(self) -> None:
        result = parse_belief('{"Cooperate": 0.5, "Defect": 0.54}', STRATEGIES)
        self.assertAlmostEqual(sum(result.values()), 1.0, places=5)

    def test_renormalisation_preserves_relative_proportions(self) -> None:
        # Sum 0.96 → renormalised. Ratio 0.6/0.36 must be preserved.
        result = parse_belief('{"Cooperate": 0.6, "Defect": 0.36}', STRATEGIES)
        ratio_before = 0.6 / 0.36
        ratio_after = result["strategy1"] / result["strategy2"]
        self.assertAlmostEqual(ratio_before, ratio_after, places=5)

    def test_missing_strategy_is_filled_with_zero(self) -> None:
        result = parse_belief('{"Cooperate": 1.0}', STRATEGIES)
        self.assertAlmostEqual(result["strategy1"], 1.0)
        self.assertAlmostEqual(result["strategy2"], 0.0)


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestErrorPaths(unittest.TestCase):
    def test_far_from_one_sum_rejected_with_specific_message(self) -> None:
        with self.assertRaises(BeliefParseError) as ctx:
            parse_belief('{"Cooperate": 5.0, "Defect": 5.0}', STRATEGIES)
        self.assertIn("sum", str(ctx.exception).lower())

    def test_negative_probability_rejected_with_specific_message(self) -> None:
        with self.assertRaises(BeliefParseError) as ctx:
            parse_belief('{"Cooperate": -0.2, "Defect": 1.2}', STRATEGIES)
        self.assertIn("negative", str(ctx.exception).lower())

    def test_only_unknown_strategy_rejected(self) -> None:
        with self.assertRaises(BeliefParseError) as ctx:
            parse_belief('{"Bogus": 1.0}', STRATEGIES)
        self.assertIn("known strategy", str(ctx.exception).lower())

    def test_invalid_json_rejected_with_json_message(self) -> None:
        with self.assertRaises(BeliefParseError) as ctx:
            parse_belief("definitely not json", STRATEGIES)
        # Message should mention "JSON" so the user knows what to fix.
        self.assertIn("json", str(ctx.exception).lower())

    def test_empty_string_rejected(self) -> None:
        with self.assertRaises(BeliefParseError) as ctx:
            parse_belief("", STRATEGIES)
        self.assertIn("empty", str(ctx.exception).lower())

    def test_whitespace_only_rejected(self) -> None:
        with self.assertRaises(BeliefParseError):
            parse_belief("   \n\t  ", STRATEGIES)

    def test_unterminated_json_rejected(self) -> None:
        with self.assertRaises(BeliefParseError) as ctx:
            parse_belief('{"Cooperate": 0.5, "Defect": 0.5', STRATEGIES)
        self.assertIn("unterminated", str(ctx.exception).lower())

    def test_zero_sum_rejected(self) -> None:
        with self.assertRaises(BeliefParseError) as ctx:
            parse_belief('{"Cooperate": 0.0, "Defect": 0.0}', STRATEGIES)
        self.assertIn("zero", str(ctx.exception).lower())

    def test_non_numeric_value_rejected(self) -> None:
        with self.assertRaises(BeliefParseError):
            parse_belief('{"Cooperate": "high", "Defect": 0.4}', STRATEGIES)

    def test_non_dict_json_rejected(self) -> None:
        # JSON list — valid JSON but not a probability map.
        with self.assertRaises(BeliefParseError):
            parse_belief("[0.5, 0.5]", STRATEGIES)

    def test_empty_object_rejected(self) -> None:
        with self.assertRaises(BeliefParseError):
            parse_belief("{}", STRATEGIES)


# ---------------------------------------------------------------------------
# Unknown extras
# ---------------------------------------------------------------------------


class TestUnknownStrategies(unittest.TestCase):
    def test_unknown_extras_dropped_when_known_present(self) -> None:
        result = parse_belief('{"Cooperate": 0.6, "Defect": 0.4, "BogusExtra": 0.99}', STRATEGIES)
        # Only the 2 declared strategies should appear in the output.
        self.assertEqual(set(result), {"strategy1", "strategy2"})

    def test_unknown_extras_dont_affect_renormalisation(self) -> None:
        # The extra "Bogus" entry has prob 100 but should be ignored;
        # remaining probs sum to 1.0 so output should be unmodified.
        result = parse_belief('{"Cooperate": 0.7, "Defect": 0.3, "Bogus": 100}', STRATEGIES)
        self.assertAlmostEqual(result["strategy1"], 0.7)
        self.assertAlmostEqual(result["strategy2"], 0.3)


# ---------------------------------------------------------------------------
# Output invariants
# ---------------------------------------------------------------------------


class TestOutputInvariants(unittest.TestCase):
    """Properties that must hold for any successfully-parsed belief."""

    def test_output_keys_are_exactly_the_strategy_keys(self) -> None:
        result = parse_belief('{"Cooperate": 0.6, "Defect": 0.4}', STRATEGIES)
        self.assertEqual(set(result.keys()), set(STRATEGIES.keys()))

    def test_probabilities_are_non_negative(self) -> None:
        result = parse_belief('{"Cooperate": 0.6, "Defect": 0.4}', STRATEGIES)
        for v in result.values():
            self.assertGreaterEqual(v, 0.0)

    def test_probabilities_sum_to_one(self) -> None:
        result = parse_belief('{"Cooperate": 0.6, "Defect": 0.4}', STRATEGIES)
        self.assertAlmostEqual(sum(result.values()), 1.0, places=5)


class TestToleranceBoundary(unittest.TestCase):
    """The reject threshold is ``5 × sum_tolerance`` from 1.0. Two
    fixtures land on each side of that boundary to pin the multiplier
    down — a mutation that swaps 5 for any other small integer would
    flip one of these."""

    def test_sum_just_inside_5x_tolerance_is_accepted(self) -> None:
        # default sum_tolerance = 0.05 → reject window |sum - 1| > 0.25.
        # Sum = 1.24 is inside (0.24 < 0.25); should renormalise.
        result = parse_belief('{"Cooperate": 0.74, "Defect": 0.50}', STRATEGIES, sum_tolerance=0.05)
        self.assertAlmostEqual(sum(result.values()), 1.0, places=5)

    def test_sum_just_outside_5x_tolerance_is_rejected(self) -> None:
        # Sum = 1.30 is outside the 0.25 window → reject.
        from src.belief_parser import BeliefParseError

        with self.assertRaises(BeliefParseError):
            parse_belief('{"Cooperate": 0.80, "Defect": 0.50}', STRATEGIES, sum_tolerance=0.05)


if __name__ == "__main__":
    unittest.main()
