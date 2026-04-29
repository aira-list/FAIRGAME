"""Tests for :class:`src.fairgame.FairGame` orchestration logic."""

from __future__ import annotations

import random
import unittest
from unittest import mock

from src.fairgame import FairGame
from src.fairgame_factory import FakeCommunicationConfig
from src.utility import CRRATransform, FehrSchmidtTransform, IdentityTransform


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _matrix_data() -> dict:
    return {
        "weights": {"w1": 3, "w2": 5, "w3": 0, "w4": 1},
        "strategies": {
            "en": {"strategy1": "Betray", "strategy2": "Cooperate"},
        },
        "combinations": {
            "c1": ["strategy1", "strategy1"],
            "c2": ["strategy1", "strategy2"],
            "c3": ["strategy2", "strategy1"],
            "c4": ["strategy2", "strategy2"],
        },
        "matrix": {
            "c1": ["w1", "w1"],
            "c2": ["w2", "w3"],
            "c3": ["w3", "w2"],
            "c4": ["w4", "w4"],
        },
    }


class _StubAgent:
    def __init__(self, name: str) -> None:
        self.name = name
        self.personality = "neutral"
        self.opponent_personality_prob = 0.0
        self.llm_service = "fake"
        self.scores: list = []
        self.strategies: list = []

    def get_info(self) -> dict:
        return {
            "name": self.name,
            "personality": self.personality,
            "llm_service": self.llm_service,
            "opponent_personality_probability": self.opponent_personality_prob,
        }

    def add_score(self, score) -> None:
        self.scores.append(score)

    def add_strategy(self, strategy: str) -> None:
        self.strategies.append(strategy)

    def last_score(self):
        return self.scores[-1]

    def last_strategy(self):
        return self.strategies[-1]


def _make_game(**kwargs) -> FairGame:
    agents = kwargs.pop("agents", None) or {
        "a1": _StubAgent("a1"),
        "a2": _StubAgent("a2"),
    }
    defaults = {
        "name": "t",
        "language": "en",
        "agents": agents,
        "n_rounds": 2,
        "n_rounds_known": True,
        "payoff_matrix_data": _matrix_data(),
        "prompt_template": "ignored",
        "stop_conditions": [],
        "agents_communicate": False,
    }
    defaults.update(kwargs)
    return FairGame(**defaults)


# ---------------------------------------------------------------------------
# Description
# ---------------------------------------------------------------------------

class TestDescription(unittest.TestCase):
    def test_description_is_property(self) -> None:
        game = _make_game()
        self.assertIsInstance(game.description, dict)
        self.assertEqual(game.description["name"], "t")

    def test_description_includes_n_rounds_and_language(self) -> None:
        game = _make_game(n_rounds=5, language="en")
        desc = game.description
        self.assertEqual(desc["n_rounds"], 5)
        self.assertEqual(desc["language"], "en")

    def test_description_includes_fake_communication_when_enabled(self) -> None:
        game = _make_game()
        game.fake_communication_config = FakeCommunicationConfig(
            enabled=True, message_count=2, base="hex"
        )
        desc = game.description
        self.assertTrue(desc["fake_communication"])
        self.assertEqual(desc["fake_message_count"], 2)
        self.assertEqual(desc["fake_message_base"], "hex")

    def test_description_omits_fake_communication_when_disabled(self) -> None:
        # No fake_communication_config attached → keys absent.
        desc = _make_game().description
        self.assertNotIn("fake_communication", desc)

    def test_description_includes_seed_when_provided(self) -> None:
        desc = _make_game(seed=42).description
        self.assertEqual(desc["seed"], 42)

    def test_description_omits_seed_when_none(self) -> None:
        desc = _make_game().description
        self.assertNotIn("seed", desc)

    def test_description_includes_equilibria_when_set(self) -> None:
        desc = _make_game(equilibria=["c4"]).description
        self.assertEqual(desc["equilibria"], ["c4"])


# ---------------------------------------------------------------------------
# Termination
# ---------------------------------------------------------------------------

class TestTermination(unittest.TestCase):
    def test_run_terminates_after_n_rounds(self) -> None:
        game = _make_game(n_rounds=2)
        with mock.patch("src.fairgame.GameRound") as cls:
            cls.return_value.run.return_value = ["strategy2", "strategy2"]  # c4
            game.run()
        self.assertEqual(game.current_round, 3)
        self.assertEqual(len(game.choices_made), 2)

    def test_run_terminates_at_stop_condition(self) -> None:
        game = _make_game(n_rounds=10, stop_conditions=["c4"])
        with mock.patch("src.fairgame.GameRound") as cls:
            cls.return_value.run.return_value = ["strategy2", "strategy2"]  # c4
            game.run()
        # Stops after round 1 since combo c4 is a stop condition.
        self.assertEqual(len(game.choices_made), 1)

    def test_stop_condition_false_when_no_rounds_played(self) -> None:
        self.assertFalse(_make_game().stop_condition_is_met())

    def test_stop_condition_false_for_unrecognised_combination(self) -> None:
        game = _make_game(stop_conditions=["c4"])
        # Manually push an invalid combination.
        game.choices_made.append(["nope", "nope"])
        self.assertFalse(game.stop_condition_is_met())

    def test_continuation_probability_can_end_game_early(self) -> None:
        # With continuation_probability=0 (the smallest valid value is
        # 0+epsilon; we use a near-zero probability with a fixed seed that
        # forces termination after round 1).
        rng = mock.Mock()
        rng.random.return_value = 0.99  # strictly above any reasonable p
        game = _make_game(
            n_rounds=10,
            continuation_probability=0.5,
            rng=rng,
        )
        with mock.patch("src.fairgame.GameRound") as cls:
            cls.return_value.run.return_value = ["strategy2", "strategy1"]
            game.run()
        # Only round 1 ran (continuation_probability check fails for round 2).
        self.assertEqual(len(game.choices_made), 1)

    def test_continuation_check_skipped_for_first_round(self) -> None:
        # Even with continuation_probability set, the first round always plays.
        rng = mock.Mock()
        rng.random.return_value = 0.99
        game = _make_game(
            n_rounds=1,
            continuation_probability=0.01,
            rng=rng,
        )
        with mock.patch("src.fairgame.GameRound") as cls:
            cls.return_value.run.return_value = ["strategy1", "strategy2"]
            game.run()
        self.assertEqual(len(game.choices_made), 1)


# ---------------------------------------------------------------------------
# Score modifiers (utility transform + discount factor)
# ---------------------------------------------------------------------------

class TestScoreModifiers(unittest.TestCase):
    def test_discount_factor_applied_to_round_two(self) -> None:
        # Round 1: discount 0.9^0 = 1.0 → raw scores preserved.
        # Round 2: discount 0.9^1 = 0.9 → halved by 0.9.
        game = _make_game(n_rounds=2, discount_factor=0.9)
        with mock.patch("src.fairgame.GameRound") as cls:
            cls.return_value.run.return_value = ["strategy1", "strategy1"]  # c1 → w1, w1 = 3, 3
            cls.return_value._update_round_history = mock.Mock()
            game.run()
        for agent in game.agents.values():
            self.assertAlmostEqual(agent.scores[0], 3.0)
            self.assertAlmostEqual(agent.scores[1], 3.0 * 0.9)

    def test_discount_factor_one_is_no_op(self) -> None:
        game = _make_game(n_rounds=2, discount_factor=1.0)
        with mock.patch("src.fairgame.GameRound") as cls:
            cls.return_value.run.return_value = ["strategy1", "strategy1"]
            cls.return_value._update_round_history = mock.Mock()
            game.run()
        for agent in game.agents.values():
            self.assertEqual(agent.scores, [3, 3])

    def test_invalid_discount_factor_rejected_at_construction(self) -> None:
        with self.assertRaises(ValueError):
            _make_game(discount_factor=0.0)
        with self.assertRaises(ValueError):
            _make_game(discount_factor=-0.1)
        with self.assertRaises(ValueError):
            _make_game(discount_factor=1.5)

    def test_invalid_continuation_probability_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _make_game(continuation_probability=0.0)
        with self.assertRaises(ValueError):
            _make_game(continuation_probability=1.5)

    def test_utility_transform_applied_per_round(self) -> None:
        # FehrSchmidt(α=0, β=0) = identity → no change.
        game = _make_game(
            n_rounds=1, utility_transform=FehrSchmidtTransform(alpha=0.0, beta=0.0)
        )
        with mock.patch("src.fairgame.GameRound") as cls:
            cls.return_value.run.return_value = ["strategy1", "strategy2"]  # c2 → 5, 0
            cls.return_value._update_round_history = mock.Mock()
            game.run()
        agents = list(game.agents.values())
        self.assertAlmostEqual(agents[0].scores[-1], 5.0)
        self.assertAlmostEqual(agents[1].scores[-1], 0.0)

    def test_default_utility_transform_is_identity(self) -> None:
        game = _make_game()
        self.assertIsInstance(game.utility_transform, IdentityTransform)


# ---------------------------------------------------------------------------
# RNG / determinism
# ---------------------------------------------------------------------------

class TestRng(unittest.TestCase):
    def test_seed_constructs_a_seeded_rng(self) -> None:
        game = _make_game(seed=42)
        self.assertIsInstance(game.rng, random.Random)

    def test_explicit_rng_takes_precedence_over_seed(self) -> None:
        my_rng = random.Random(123)
        game = _make_game(rng=my_rng, seed=999)
        self.assertIs(game.rng, my_rng)

    def test_two_games_with_same_seed_have_same_rng_sequence(self) -> None:
        a = _make_game(seed=7)
        b = _make_game(seed=7)
        # Pull the same number of values from each.
        seq_a = [a.rng.random() for _ in range(20)]
        seq_b = [b.rng.random() for _ in range(20)]
        self.assertEqual(seq_a, seq_b)


# ---------------------------------------------------------------------------
# Reputation-applies wiring
# ---------------------------------------------------------------------------

class TestCompoundDiscountWarning(unittest.TestCase):
    """Combining discount factor with continuation probability double-counts
    the effective discount; we want a clear warning when the user does both
    (without forbidding the combination)."""

    def test_warning_logged_when_both_set(self) -> None:
        with self.assertLogs("src.fairgame", level="WARNING") as cm:
            _make_game(discount_factor=0.9, continuation_probability=0.95)
        joined = "\n".join(cm.output)
        self.assertIn("discount", joined.lower())
        self.assertIn("continuation", joined.lower())

    def test_no_warning_when_only_discount_set(self) -> None:
        # Pure discount factor → no warning.
        import logging

        with mock.patch.object(
            __import__("src.fairgame", fromlist=["logger"]).logger,
            "warning",
        ) as warn:
            _make_game(discount_factor=0.9)
            warn.assert_not_called()

    def test_no_warning_when_only_continuation_set(self) -> None:
        import logging

        with mock.patch.object(
            __import__("src.fairgame", fromlist=["logger"]).logger,
            "warning",
        ) as warn:
            _make_game(continuation_probability=0.95)
            warn.assert_not_called()

    def test_no_warning_when_discount_is_one(self) -> None:
        # Discount=1.0 means no discounting — combining with continuation
        # is the canonical stochastic-horizon model and shouldn't warn.
        import logging

        with mock.patch.object(
            __import__("src.fairgame", fromlist=["logger"]).logger,
            "warning",
        ) as warn:
            _make_game(discount_factor=1.0, continuation_probability=0.95)
            warn.assert_not_called()


class TestReputationAppliesWiring(unittest.TestCase):
    def test_default_value_true(self) -> None:
        game = _make_game()
        self.assertTrue(game.reputation_applies)

    def test_constructor_accepts_reputation_applies_false(self) -> None:
        game = _make_game(reputation_applies=False)
        self.assertFalse(game.reputation_applies)

    def test_description_surfaces_reputation_applies(self) -> None:
        # When False, the description must mention so a downstream consumer
        # (results_processor, GUI) knows the labels are suppressed.
        desc = _make_game(reputation_applies=False).description
        self.assertEqual(desc.get("reputation_applies"), False)


if __name__ == "__main__":
    unittest.main()
