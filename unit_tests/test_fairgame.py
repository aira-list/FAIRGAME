"""Tests for :class:`src.fairgame.FairGame` orchestration logic."""

from __future__ import annotations

import unittest
from unittest import mock

from src.fairgame import FairGame
from src.fairgame_factory import FakeCommunicationConfig


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


def _make_game(stop_conditions=None, n_rounds=2) -> FairGame:
    agents = {"a1": _StubAgent("a1"), "a2": _StubAgent("a2")}
    return FairGame(
        name="t",
        language="en",
        agents=agents,
        n_rounds=n_rounds,
        n_rounds_known=True,
        payoff_matrix_data=_matrix_data(),
        prompt_template="ignored",
        stop_conditions=stop_conditions or [],
        agents_communicate=False,
    )


class TestFairGame(unittest.TestCase):
    def test_description_is_property_not_method(self) -> None:
        game = _make_game()
        # Reading the property must yield a dict; treating it as a callable
        # would have raised TypeError previously.
        self.assertIsInstance(game.description, dict)
        self.assertEqual(game.description["name"], "t")

    def test_description_includes_fake_communication_when_enabled(self) -> None:
        game = _make_game()
        game.fake_communication_config = FakeCommunicationConfig(
            enabled=True, message_count=2, base="hex"
        )
        desc = game.description
        self.assertTrue(desc["fake_communication"])
        self.assertEqual(desc["fake_message_count"], 2)
        self.assertEqual(desc["fake_message_base"], "hex")

    def test_run_terminates_after_n_rounds(self) -> None:
        game = _make_game(n_rounds=2)
        with mock.patch("src.fairgame.GameRound") as game_round_cls:
            instance = game_round_cls.return_value
            instance.run.return_value = ["strategy2", "strategy2"]  # combo4
            game.run()
            self.assertEqual(game.current_round, 3)
            self.assertEqual(len(game.choices_made), 2)

    def test_run_stops_when_stop_condition_observed(self) -> None:
        game = _make_game(n_rounds=10, stop_conditions=["c4"])
        with mock.patch("src.fairgame.GameRound") as game_round_cls:
            instance = game_round_cls.return_value
            instance.run.return_value = ["strategy2", "strategy2"]  # combo c4
            game.run()
            # Stops after the first round because combo4 is a stop condition.
            self.assertEqual(len(game.choices_made), 1)

    def test_stop_condition_not_met_when_no_history(self) -> None:
        self.assertFalse(_make_game().stop_condition_is_met())


if __name__ == "__main__":
    unittest.main()
