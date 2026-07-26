"""The nested ``agents.types.commonKnowledge`` flag must reach the engine.

The factory extracts the nested flag into ``types_config``, but the engine
gates the ``{typeDistribution}`` prompt placeholder on the game's
``types_common_knowledge`` (raw key ``typesAreCommonKnowledge``). A config
using only the nested spelling silently ran WITHOUT common knowledge while
its description claimed otherwise.
"""

from __future__ import annotations

import unittest

from src.factory.fairgame_factory import FairGameFactory


def _config(types_block: dict, **top_level) -> dict:
    cfg = {
        "name": "types_demo",
        "nRounds": 1,
        "nRoundsIsKnown": True,
        "languages": ["en"],
        "allAgentPermutations": False,
        "agents": {
            "names": ["a", "b"],
            "personalities": {"en": ["nice", "mean"]},
            "opponentPersonalityProb": [0, 0],
            "types": types_block,
        },
        "llms": ["Baseline:TitForTat", "Baseline:TitForTat"],
        "promptTemplate": {"en": "(baseline game; never read)"},
        "payoffMatrix": {
            "weights": {"w1": 1, "w2": 2},
            "strategies": {"en": {"strategy1": "X", "strategy2": "Y"}},
            "combinations": {
                "c1": ["strategy1", "strategy1"],
                "c2": ["strategy2", "strategy2"],
            },
            "matrix": {"c1": ["w1", "w1"], "c2": ["w2", "w2"]},
        },
        "stopGameWhen": [],
        "agentsCommunicate": False,
        "seed": 7,
    }
    cfg.update(top_level)
    return cfg


class TestNestedCommonKnowledgeWiring(unittest.TestCase):
    def test_nested_flag_reaches_engine(self) -> None:
        cfg = _config({"labels": ["T1", "T2"], "commonKnowledge": True})
        game = FairGameFactory().create_games(cfg)[0]
        self.assertTrue(game.types_common_knowledge)
        self.assertEqual(game.types_config["labels"], ["T1", "T2"])

    def test_nested_flag_defaults_off(self) -> None:
        cfg = _config({"labels": ["T1", "T2"]})
        game = FairGameFactory().create_games(cfg)[0]
        self.assertFalse(game.types_common_knowledge)

    def test_top_level_key_wins_over_nested(self) -> None:
        cfg = _config(
            {"labels": ["T1", "T2"], "commonKnowledge": True},
            typesAreCommonKnowledge=False,
        )
        game = FairGameFactory().create_games(cfg)[0]
        self.assertFalse(game.types_common_knowledge)


if __name__ == "__main__":
    unittest.main()
