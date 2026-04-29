"""Tests for :mod:`src.belief_parser`."""

from __future__ import annotations

import unittest

from src.belief_parser import BeliefParseError, parse_belief

STRATEGIES = {"strategy1": "Cooperate", "strategy2": "Defect"}


class TestParseBelief(unittest.TestCase):
    def test_parses_clean_json_with_display_labels(self) -> None:
        result = parse_belief('{"Cooperate": 0.7, "Defect": 0.3}', STRATEGIES)
        self.assertAlmostEqual(result["strategy1"], 0.7)
        self.assertAlmostEqual(result["strategy2"], 0.3)

    def test_parses_canonical_keys(self) -> None:
        result = parse_belief('{"strategy1": 0.6, "strategy2": 0.4}', STRATEGIES)
        self.assertAlmostEqual(result["strategy1"], 0.6)
        self.assertAlmostEqual(result["strategy2"], 0.4)

    def test_extracts_json_from_surrounding_prose(self) -> None:
        text = 'Sure! Here is my belief: {"Cooperate": 0.5, "Defect": 0.5}. Hope this helps.'
        result = parse_belief(text, STRATEGIES)
        self.assertAlmostEqual(result["strategy1"], 0.5)

    def test_renormalises_within_tolerance(self) -> None:
        # Sum = 1.04, within tolerance window — accepted and renormalised.
        result = parse_belief('{"Cooperate": 0.5, "Defect": 0.54}', STRATEGIES)
        self.assertAlmostEqual(sum(result.values()), 1.0, places=5)

    def test_rejects_far_from_one_sum(self) -> None:
        with self.assertRaises(BeliefParseError):
            parse_belief('{"Cooperate": 5.0, "Defect": 5.0}', STRATEGIES)

    def test_rejects_negative_probability(self) -> None:
        with self.assertRaises(BeliefParseError):
            parse_belief('{"Cooperate": -0.2, "Defect": 1.2}', STRATEGIES)

    def test_rejects_unknown_strategy_only(self) -> None:
        with self.assertRaises(BeliefParseError):
            parse_belief('{"Bogus": 1.0}', STRATEGIES)

    def test_unknown_strategy_keys_are_ignored(self) -> None:
        # If at least one key is recognised, unknowns are dropped silently.
        result = parse_belief(
            '{"Cooperate": 0.6, "Defect": 0.4, "BogusExtra": 0.99}', STRATEGIES
        )
        self.assertEqual(set(result), {"strategy1", "strategy2"})

    def test_missing_strategy_filled_with_zero(self) -> None:
        result = parse_belief('{"Cooperate": 1.0}', STRATEGIES)
        self.assertAlmostEqual(result["strategy1"], 1.0)
        self.assertAlmostEqual(result["strategy2"], 0.0)

    def test_invalid_json_raises(self) -> None:
        with self.assertRaises(BeliefParseError):
            parse_belief("definitely not json", STRATEGIES)

    def test_empty_response_raises(self) -> None:
        with self.assertRaises(BeliefParseError):
            parse_belief("", STRATEGIES)


if __name__ == "__main__":
    unittest.main()
