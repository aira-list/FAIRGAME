"""Tests for prompt-side (behavioural) discount and risk framing.

These features let a discount factor or a CRRA risk preference be described
to the agent in the prompt (so it shapes the LLM's *choices*) instead of, or
in addition to, being applied to the recorded score. The key invariant is
that a preference in ``"prompt"`` mode is NOT also applied to the score —
otherwise the same preference would be counted as both treatment and
measurement.
"""

from __future__ import annotations

import unittest

from src.fairgame import FairGame
from src.game_config import GameConfig
from src.payoff_matrix import PayoffMatrix
from src.prompt_creator import PromptCreator
from src.utility import CRRATransform

PM_DATA = {
    "weights": {"weight1": 6, "weight2": 10, "weight3": 0, "weight4": 2},
    "strategies": {"en": {"strategy1": "Cooperate", "strategy2": "Defect"}},
    "combinations": {
        "combination1": ["strategy1", "strategy1"],
        "combination2": ["strategy1", "strategy2"],
        "combination3": ["strategy2", "strategy1"],
        "combination4": ["strategy2", "strategy2"],
    },
    "matrix": {
        "combination1": ["weight1", "weight1"],
        "combination2": ["weight3", "weight2"],
        "combination3": ["weight2", "weight3"],
        "combination4": ["weight4", "weight4"],
    },
}

TEMPLATE = (
    "You are {currentPlayerName}. Round {currentRound}.\n"
    "If you both choose {strategy1}, penalty {weight1}.\n"
    "Your goal is to minimise penalty.\n"
    "{discount}: [Later rounds weigh less heavily on you.]\n"
    "{riskFrame}: [You are risk-averse and prefer certainty.]\n"
    "History: {history}.\n"
    "Choose between {strategy1} and {strategy2}."
)

DISCOUNT_TEXT = "Later rounds weigh less heavily"
RISK_TEXT = "risk-averse"


class _StubAgent:
    def __init__(self, name: str) -> None:
        self.name = name
        self.personality = "None"
        self.strategies: list = []


class _StubOpponent:
    def __init__(self, name: str) -> None:
        self.name = name
        self.personality = "None"
        self.opponent_personality_prob = 0
        self.strategies: list = []


def _render(*, discount_in_prompt: bool, risk_in_prompt: bool, delta: float = 0.9) -> str:
    pm = PayoffMatrix(PM_DATA, "en")
    pc = PromptCreator(
        "en",
        TEMPLATE,
        5,
        True,
        pm,
        discount_in_prompt=discount_in_prompt,
        discount_factor=delta,
        risk_in_prompt=risk_in_prompt,
    )
    return pc.fill_template(_StubAgent("a1"), [_StubOpponent("a2")], 2, {}, "choose")


class TestPromptSideFraming(unittest.TestCase):
    def test_blocks_absent_by_default(self) -> None:
        out = _render(discount_in_prompt=False, risk_in_prompt=False)
        self.assertNotIn(DISCOUNT_TEXT, out)
        self.assertNotIn(RISK_TEXT, out)

    def test_blocks_present_when_enabled(self) -> None:
        out = _render(discount_in_prompt=True, risk_in_prompt=True)
        self.assertIn(DISCOUNT_TEXT, out)
        self.assertIn(RISK_TEXT, out)

    def test_discount_block_stripped_when_delta_is_one(self) -> None:
        # No actual discounting -> nothing to tell the agent.
        out = _render(discount_in_prompt=True, risk_in_prompt=False, delta=1.0)
        self.assertNotIn(DISCOUNT_TEXT, out)

    def test_each_block_independent(self) -> None:
        out = _render(discount_in_prompt=True, risk_in_prompt=False)
        self.assertIn(DISCOUNT_TEXT, out)
        self.assertNotIn(RISK_TEXT, out)


class _ScoreAgent:
    def __init__(self, name: str, score: float) -> None:
        self.name = name
        self.scores = [score]


def _game(*, risk_mode: str, discount_mode: str) -> FairGame:
    config = GameConfig(
        name="t",
        language="en",
        n_rounds=2,
        n_rounds_known=True,
        payoff_matrix_data=PM_DATA,
        prompt_template="x",
        stop_conditions=[],
        agents_communicate=False,
        utility_transform=CRRATransform(gamma=0.5, offset=1.0),
        discount_factor=0.9,
        discount_mode=discount_mode,
        risk_mode=risk_mode,
    )
    g = FairGame.from_config(config, {})
    g.agents = {"a1": _ScoreAgent("a1", 6.0), "a2": _ScoreAgent("a2", 0.0)}
    g.current_round = 2  # so discount = 0.9**1 when applied
    return g


class TestScoreModifierGating(unittest.TestCase):
    def test_score_mode_applies_transform_and_discount(self) -> None:
        g = _game(risk_mode="score", discount_mode="score")
        g._finalise_round_scores()
        # CRRA(gamma=.5) on 6 (+1 offset) then *0.9; definitely not the raw 6.
        self.assertNotAlmostEqual(g.agents["a1"].scores[-1], 6.0, places=3)
        self.assertLess(g.agents["a1"].scores[-1], 6.0)

    def test_prompt_mode_leaves_raw_score_untouched(self) -> None:
        g = _game(risk_mode="prompt", discount_mode="prompt")
        g._finalise_round_scores()
        # Behavioural-only: no transform, no discount on the score.
        self.assertAlmostEqual(g.agents["a1"].scores[-1], 6.0, places=6)
        self.assertAlmostEqual(g.agents["a2"].scores[-1], 0.0, places=6)

    def test_both_mode_applies_to_score(self) -> None:
        g = _game(risk_mode="both", discount_mode="both")
        g._finalise_round_scores()
        self.assertLess(g.agents["a1"].scores[-1], 6.0)

    def test_mixed_modes(self) -> None:
        # Discount behavioural (prompt), risk analytical (score): transform
        # applies, discount does not.
        g = _game(risk_mode="score", discount_mode="prompt")
        g._finalise_round_scores()
        transformed = CRRATransform(gamma=0.5, offset=1.0).transform([6.0])[0]
        self.assertAlmostEqual(g.agents["a1"].scores[-1], transformed, places=6)


if __name__ == "__main__":
    unittest.main()
