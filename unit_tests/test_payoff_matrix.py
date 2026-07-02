"""Unit tests for :class:`src.payoff_matrix.PayoffMatrix`."""

from __future__ import annotations

import unittest

from src.payoff_matrix import PayoffMatrix

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _pd_matrix() -> dict:
    return {
        "weights": {"w1": 3, "w2": 5, "w3": 0, "w4": 1},
        "strategies": {
            "en": {"strategy1": "Betray", "strategy2": "Cooperate"},
            "fr": {"strategy1": "Trahir", "strategy2": "Coopérer"},
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


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


class TestProperties(unittest.TestCase):
    def setUp(self) -> None:
        self.pm = PayoffMatrix(_pd_matrix(), "en")

    def test_strategies_returns_language_specific_dict(self) -> None:
        self.assertEqual(self.pm.strategies, {"strategy1": "Betray", "strategy2": "Cooperate"})

    def test_strategies_uses_specified_language(self) -> None:
        fr = PayoffMatrix(_pd_matrix(), "fr")
        self.assertEqual(fr.strategies["strategy1"], "Trahir")

    def test_weights_returns_unaltered_weights_dict(self) -> None:
        self.assertEqual(self.pm.weights, {"w1": 3, "w2": 5, "w3": 0, "w4": 1})

    def test_matrix_returns_combination_to_weight_keys(self) -> None:
        self.assertEqual(self.pm.matrix["combo1"], ["w1", "w1"])
        self.assertEqual(self.pm.matrix["combo2"], ["w2", "w3"])


# ---------------------------------------------------------------------------
# get_weights_for_combination
# ---------------------------------------------------------------------------


class TestGetWeightsForCombination(unittest.TestCase):
    def setUp(self) -> None:
        self.pm = PayoffMatrix(_pd_matrix(), "en")

    def test_resolves_each_canonical_combination(self) -> None:
        self.assertEqual(self.pm.get_weights_for_combination(["Betray", "Betray"]), (3, 3))
        self.assertEqual(self.pm.get_weights_for_combination(["Betray", "Cooperate"]), (5, 0))
        self.assertEqual(self.pm.get_weights_for_combination(["Cooperate", "Betray"]), (0, 5))
        self.assertEqual(self.pm.get_weights_for_combination(["Cooperate", "Cooperate"]), (1, 1))

    def test_returns_tuple_not_list(self) -> None:
        # Tuples are hashable and immutable — guard the contract.
        result = self.pm.get_weights_for_combination(["Betray", "Betray"])
        self.assertIsInstance(result, tuple)

    def test_unknown_strategy_raises_value_error_with_label(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            self.pm.get_weights_for_combination(["Bogus", "Betray"])
        self.assertIn("Bogus", str(ctx.exception))

    def test_combination_not_in_matrix_raises_value_error(self) -> None:
        # Build a matrix where one combination is intentionally missing.
        data = _pd_matrix()
        del data["combinations"]["combo3"]
        del data["matrix"]["combo3"]
        pm = PayoffMatrix(data, "en")
        with self.assertRaises(ValueError) as ctx:
            pm.get_weights_for_combination(["Cooperate", "Betray"])
        self.assertIn("combination", str(ctx.exception).lower())


# ---------------------------------------------------------------------------
# get_combination_key
# ---------------------------------------------------------------------------


class TestGetCombinationKey(unittest.TestCase):
    def setUp(self) -> None:
        self.pm = PayoffMatrix(_pd_matrix(), "en")

    def test_round_trips_strategy_keys_to_combo_name(self) -> None:
        self.assertEqual(self.pm.get_combination_key(["strategy1", "strategy2"]), "combo2")
        self.assertEqual(self.pm.get_combination_key(["strategy2", "strategy1"]), "combo3")

    def test_unknown_combination_raises_with_meaningful_message(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            self.pm.get_combination_key(["nope", "nope"])
        self.assertIn("not found", str(ctx.exception).lower())


# ---------------------------------------------------------------------------
# attribute_scores
# ---------------------------------------------------------------------------


class TestAttributeScores(unittest.TestCase):
    def setUp(self) -> None:
        self.pm = PayoffMatrix(_pd_matrix(), "en")

    def test_scores_are_assigned_in_agent_order(self) -> None:
        a, b = _StubAgent(), _StubAgent()
        # combo2 → weight keys [w2, w3] → values 5, 0.
        self.pm.attribute_scores([a, b], ["strategy1", "strategy2"])
        self.assertEqual(a.scores, [5])
        self.assertEqual(b.scores, [0])

    def test_scores_are_appended_not_replaced(self) -> None:
        a, b = _StubAgent(), _StubAgent()
        a.scores.append(99)  # pre-existing history
        self.pm.attribute_scores([a, b], ["strategy1", "strategy1"])
        self.assertEqual(a.scores, [99, 3])
        self.assertEqual(b.scores, [3])

    def test_attribute_scores_total_invariant(self) -> None:
        # For each combination, sum of attributed scores equals sum of the
        # combination's weight values.
        weights = {"w1": 3, "w2": 5, "w3": 0, "w4": 1}
        for combo_keys in [
            ["strategy1", "strategy1"],
            ["strategy1", "strategy2"],
            ["strategy2", "strategy1"],
            ["strategy2", "strategy2"],
        ]:
            a, b = _StubAgent(), _StubAgent()
            self.pm.attribute_scores([a, b], combo_keys)
            combo_name = self.pm.get_combination_key(combo_keys)
            expected_total = sum(weights[k] for k in self.pm.matrix[combo_name])
            self.assertEqual(a.scores[-1] + b.scores[-1], expected_total)

    def test_attribute_scores_unknown_combination_raises(self) -> None:
        a, b = _StubAgent(), _StubAgent()
        with self.assertRaises(ValueError):
            self.pm.attribute_scores([a, b], ["nope", "nope"])


# ---------------------------------------------------------------------------
# Lazy combo cache
# ---------------------------------------------------------------------------


class TestComboCache(unittest.TestCase):
    def test_cache_is_built_lazily(self) -> None:
        pm = PayoffMatrix(_pd_matrix(), "en")
        self.assertIsNone(pm._combo_by_strategies_cache)
        _ = pm._combo_by_strategies  # access triggers build
        self.assertIsNotNone(pm._combo_by_strategies_cache)

    def test_cache_is_reused_between_accesses(self) -> None:
        pm = PayoffMatrix(_pd_matrix(), "en")
        first = pm._combo_by_strategies
        second = pm._combo_by_strategies
        self.assertIs(first, second)

    def test_legacy_pair_combinations_dont_break_cache(self) -> None:
        # The legacy [strategy, weight] pair format will fail to be hashed
        # inline; the cache should only build when actually used. Build a
        # PayoffMatrix from the legacy shape and confirm the constructor
        # itself doesn't blow up.
        legacy = _pd_matrix()
        legacy["combinations"] = {
            "combo1": [["strategy1", "w1"], ["strategy1", "w1"]],
            "combo2": [["strategy1", "w2"], ["strategy2", "w3"]],
        }
        pm = PayoffMatrix(legacy, "en")
        # The cache is unbuilt; the engine validator transforms before
        # PayoffMatrix is used in earnest. Just verify construction works.
        self.assertIsNone(pm._combo_by_strategies_cache)


class TestAttributeScoresOrder(unittest.TestCase):
    """attribute_scores pops weight_keys in agent order — pinning
    asymmetric weights tests this. Existing tests use a symmetric PD
    where (3, 5) on combo3 = (5, 3) on combo2, so a swap mutation
    survives. This test uses an asymmetric configuration to detect it."""

    def test_first_agent_gets_first_weight_second_gets_second(self) -> None:
        # (strategy1, strategy2) → combo2 with weight_keys [w2, w3] = [5, 0].
        # Agent order: a=strategy1, b=strategy2 → a:5, b:0. A loop that
        # iterated in reverse, popped from the end, or zipped backwards
        # would give the swapped pair (0, 5).
        from src.payoff_matrix import PayoffMatrix

        pm = PayoffMatrix(_pd_matrix(), "en")
        a, b = _StubAgent(), _StubAgent()
        pm.attribute_scores([a, b], ["strategy1", "strategy2"])
        self.assertEqual(a.scores[-1], 5)
        self.assertEqual(b.scores[-1], 0)


if __name__ == "__main__":
    unittest.main()
