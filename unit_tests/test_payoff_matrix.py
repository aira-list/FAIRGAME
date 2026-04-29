"""Unit tests for :class:`src.payoff_matrix.PayoffMatrix`."""

from __future__ import annotations

import unittest

from src.payoff_matrix import PayoffMatrix


def _matrix() -> dict:
    return {
        "weights": {"w1": 3, "w2": 5, "w3": 0, "w4": 1},
        "strategies": {
            "en": {"strategy1": "Betray", "strategy2": "Cooperate"},
        },
        "combinations": {
            "combo1": ["strategy1", "strategy1"],
            "combo2": ["strategy1", "strategy2"],
            "combo3": ["strategy2", "strategy1"],
            "combo4": ["strategy2", "strategy2"],
        },
        "matrix": {
            "combo1": ["w1", "w1"],
            "combo2": ["w2", "w3"],
            "combo3": ["w3", "w2"],
            "combo4": ["w4", "w4"],
        },
    }


class _StubAgent:
    def __init__(self) -> None:
        self.scores: list = []

    def add_score(self, score) -> None:
        self.scores.append(score)


class TestPayoffMatrix(unittest.TestCase):
    def setUp(self) -> None:
        self.pm = PayoffMatrix(_matrix(), "en")

    def test_get_weights_for_combination_resolves_named_strategies(self) -> None:
        self.assertEqual(self.pm.get_weights_for_combination(["Betray", "Betray"]), (3, 3))
        self.assertEqual(self.pm.get_weights_for_combination(["Betray", "Cooperate"]), (5, 0))
        self.assertEqual(self.pm.get_weights_for_combination(["Cooperate", "Cooperate"]), (1, 1))

    def test_get_weights_for_combination_unknown_strategy_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.pm.get_weights_for_combination(["Bogus", "Betray"])

    def test_get_combination_key_round_trip(self) -> None:
        self.assertEqual(self.pm.get_combination_key(["strategy1", "strategy2"]), "combo2")

    def test_get_combination_key_unknown_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.pm.get_combination_key(["nope", "nope"])

    def test_attribute_scores_assigns_in_order(self) -> None:
        a, b = _StubAgent(), _StubAgent()
        self.pm.attribute_scores([a, b], ["strategy1", "strategy2"])
        # combo2 -> [w2=5, w3=0]
        self.assertEqual(a.scores, [5])
        self.assertEqual(b.scores, [0])

    def test_combo_lookup_is_cached(self) -> None:
        # Trigger the lazy build, then confirm the cache hit returns same dict.
        first = self.pm._combo_by_strategies
        second = self.pm._combo_by_strategies
        self.assertIs(first, second)


if __name__ == "__main__":
    unittest.main()
