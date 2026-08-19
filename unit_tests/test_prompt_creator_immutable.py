"""Deepening #2 — prompt rendering must be side-effect-free across renders.

Before: ``fill_template`` mutated ``self.prompt_template`` in place, so a second
render on the same instance operated on an already-stripped template. The
interface now reads as "construct once, render(phase) many times" — each render
starts from the original template.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from src.prompting.prompt_creator import PromptCreator

_TEMPLATE = (
    "You are {currentPlayerName} vs {opponent1}. "
    "{choose}: [Choose {strategy1} or {strategy2}.] "
    "{believe}: [Predict {opponent1}.]"
)


def _make_creator() -> PromptCreator:
    payoff = SimpleNamespace(
        strategies={"strategy1": "Cooperate", "strategy2": "Defect"},
        weights={"weight1": 3, "weight2": 5, "weight3": 0, "weight4": 1},
    )
    return PromptCreator("en", _TEMPLATE, n_rounds=3, n_rounds_known=True, payoff_matrix=payoff)


class TestPromptRenderIsReusable(unittest.TestCase):
    def test_two_phases_on_same_instance(self) -> None:
        creator = _make_creator()
        agent = SimpleNamespace(name="alice")
        opps = [SimpleNamespace(name="bob")]

        choose = creator.fill_template(agent, opps, 1, {}, phase="choose")
        believe = creator.fill_template(agent, opps, 1, {}, phase="believe")

        # Each render keeps only its own phase block — proving the second
        # render did not inherit the first render's stripped template.
        self.assertIn("Choose", choose)
        self.assertNotIn("Predict", choose)
        self.assertIn("Predict", believe)
        self.assertNotIn("Choose", believe)

    def test_repeated_render_is_stable(self) -> None:
        creator = _make_creator()
        agent = SimpleNamespace(name="alice")
        opps = [SimpleNamespace(name="bob")]
        first = creator.fill_template(agent, opps, 1, {}, phase="choose")
        second = creator.fill_template(agent, opps, 1, {}, phase="choose")
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
