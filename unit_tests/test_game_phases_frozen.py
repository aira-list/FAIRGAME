"""Deepening #5 — the phase list is an explicit, resolved-once game property.

Before: ``GameRound.run`` called ``phases_for_game(game)`` every round, deriving
control flow from mutable game attributes each time. Now ``FairGame.phases``
resolves once (lazily, after the factory finishes setup) and freezes.
"""

from __future__ import annotations

import random
import unittest

from src.agents.agent import LLMAgent
from src.game.fairgame import FairGame
from src.game.game_config import GameConfig
from src.game.phases import BeliefPhase, BeliefSecondOrderPhase, ChoosePhase

_MATRIX = {"strategies": {"en": {}}, "weights": {}, "combinations": {}, "matrix": {}}


def _game(**raw_overrides) -> FairGame:
    raw = {
        "name": "g",
        "nRounds": 2,
        "nRoundsIsKnown": True,
        "stopGameWhen": [],
        "agentsCommunicate": False,
    }
    raw.update(raw_overrides)
    cfg = GameConfig.from_raw(
        raw,
        language="en",
        payoff_matrix_data=_MATRIX,
        prompt_template="T",
        types_config=None,
        rng=random.Random(1),
        seed=1,
    )
    agents = {
        n: LLMAgent(
            name=n, llm_service="OpenAIGPT4o", personality="p", opponent_personality_prob=0.5
        )
        for n in ("a", "b")
    }
    return FairGame.from_config(cfg, agents)


class TestGamePhasesFrozen(unittest.TestCase):
    def test_cached_same_object(self) -> None:
        game = _game()
        self.assertIs(game.phases, game.phases)

    def test_reflects_config(self) -> None:
        game = _game(elicitBeliefs=True, tomOrder=2)
        types = [type(p) for p in game.phases]
        self.assertIn(BeliefPhase, types)
        self.assertIn(BeliefSecondOrderPhase, types)
        self.assertIs(type(game.phases[-1]), ChoosePhase)

    def test_frozen_after_first_access(self) -> None:
        game = _game(elicitBeliefs=True, tomOrder=1)
        _ = game.phases  # resolve + freeze
        game.config.elicit_beliefs = False  # mutate after the fact
        # Still frozen to the resolved list — control flow no longer drifts
        # with mid-game attribute mutation.
        self.assertIn(BeliefPhase, [type(p) for p in game.phases])


if __name__ == "__main__":
    unittest.main()
