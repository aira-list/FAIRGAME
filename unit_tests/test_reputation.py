"""Tests for the {coopRateN} / {reputationN} prompt placeholders."""

from __future__ import annotations

import unittest

from src.payoff_matrix import PayoffMatrix
from src.prompt_creator import PromptCreator


def _matrix_data() -> dict:
    return {
        "weights": {"weight1": 6, "weight2": 10, "weight3": 0, "weight4": 2},
        "strategies": {"en": {"strategy1": "Cooperate", "strategy2": "Defect"}},
        "combinations": {
            "c1": ["strategy1", "strategy1"],
            "c2": ["strategy2", "strategy2"],
        },
        "matrix": {"c1": ["weight1", "weight1"], "c2": ["weight4", "weight4"]},
    }


class _StubAgent:
    def __init__(self, name: str, personality: str = "neutral") -> None:
        self.name = name
        self.personality = personality
        self.opponent_personality_prob = 0.0


def _make_creator(reputation_window=None) -> PromptCreator:
    pm = PayoffMatrix(_matrix_data(), "en")
    return PromptCreator(
        "en",
        "{currentPlayerName} faces {opponent1} (coop rate {coopRate1}, "
        "reputation {reputation1}). {choose}: [Pick {strategy1} or {strategy2}.]",
        n_rounds=10,
        n_rounds_known=False,
        payoff_matrix=pm,
        reputation_window=reputation_window,
    )


class TestReputationPlaceholders(unittest.TestCase):
    def setUp(self) -> None:
        self.history = {
            "round_1": {"opp": {"strategy": "Cooperate"}},
            "round_2": {"opp": {"strategy": "Cooperate"}},
            "round_3": {"opp": {"strategy": "Defect"}},
            "round_4": {"opp": {"strategy": "Defect"}},
        }

    def test_full_history_average(self) -> None:
        creator = _make_creator()
        agent = _StubAgent("agent1")
        opp = _StubAgent("opp")
        prompt = creator.fill_template(agent, [opp], 5, self.history, "choose")
        # 2 cooperate / 4 total = 0.50.
        self.assertIn("coop rate 0.50", prompt)
        self.assertIn("reputation moderately cooperative", prompt)

    def test_recent_window_only(self) -> None:
        creator = _make_creator(reputation_window=2)
        agent = _StubAgent("agent1")
        opp = _StubAgent("opp")
        prompt = creator.fill_template(agent, [opp], 5, self.history, "choose")
        # Last 2 rounds were Defect / Defect → coop rate 0.00.
        self.assertIn("coop rate 0.00", prompt)
        self.assertIn("reputation uncooperative", prompt)

    def test_no_history_yields_unknown(self) -> None:
        creator = _make_creator()
        agent = _StubAgent("agent1")
        opp = _StubAgent("opp")
        prompt = creator.fill_template(agent, [opp], 1, {}, "choose")
        self.assertIn("coop rate n/a", prompt)
        self.assertIn("reputation unknown", prompt)


if __name__ == "__main__":
    unittest.main()
