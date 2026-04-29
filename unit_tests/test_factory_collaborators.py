"""Tests for the new factory-collaborator classes.

The factory used to be a 350-line god class. It's now split into:

* :class:`PermutationExpander` — owns the personality / opponent-prior /
  agent / language permutation DataFrame.
* :class:`TournamentBuilder` — generates per-pair configs for round-robin
  tournaments.
"""

from __future__ import annotations

import unittest

from src.factory import PermutationExpander, TournamentBuilder


def _agents_block() -> dict:
    return {
        "names": ["a", "b"],
        "personalities": {"en": ["nice", "mean"]},
        "opponentPersonalityProb": [0],
    }


def _config(**overrides) -> dict:
    cfg = {
        "name": "demo",
        "nRounds": 1,
        "nRoundsIsKnown": True,
        "languages": ["en"],
        "agents": _agents_block(),
        "llm": "OpenAIGPT4o",
        "allAgentPermutations": True,
    }
    cfg.update(overrides)
    return cfg


# ---------------------------------------------------------------------------
# PermutationExpander
# ---------------------------------------------------------------------------

class TestPermutationExpanderHomogeneousLLM(unittest.TestCase):
    def test_dedups_symmetric_pairs_with_same_llm(self) -> None:
        # 2 personalities × 2 agents with shared LLM →
        # combinations_with_replacement → 3 dedup'd pairs.
        df = PermutationExpander().expand(_config(), language="en")
        self.assertEqual(len(df), 3)

    def test_attaches_per_agent_llm_columns(self) -> None:
        df = PermutationExpander().expand(_config(), language="en")
        self.assertIn("LLM1", df.columns)
        self.assertIn("LLM2", df.columns)
        self.assertTrue((df["LLM1"] == "OpenAIGPT4o").all())

    def test_language_column_set_correctly(self) -> None:
        df = PermutationExpander().expand(_config(), language="en")
        self.assertTrue((df["Language"] == "en").all())


class TestPermutationExpanderMixedLLM(unittest.TestCase):
    def test_full_product_when_llms_differ_per_agent(self) -> None:
        cfg = _config()
        cfg.pop("llm")
        cfg["llms"] = {"a": "OpenAIGPT4o", "b": "Claude35Sonnet"}
        df = PermutationExpander().expand(cfg, language="en")
        # 2 personalities^2 = 4 (no dedup with mixed LLMs).
        self.assertEqual(len(df), 4)


class TestPermutationExpanderSinglePath(unittest.TestCase):
    def test_compute_configuration_emits_one_row(self) -> None:
        cfg = _config(allAgentPermutations=False)
        cfg["agents"]["personalities"]["en"] = ["nice", "mean"]
        cfg["agents"]["opponentPersonalityProb"] = [0, 0]
        df = PermutationExpander().expand(cfg, language="en")
        self.assertEqual(len(df), 1)


# ---------------------------------------------------------------------------
# TournamentBuilder
# ---------------------------------------------------------------------------

class TestTournamentBuilder(unittest.TestCase):
    def test_round_robin_with_three_agents_yields_three_pairs(self) -> None:
        builder = TournamentBuilder()
        names = ["a", "b", "c"]
        pairs = builder.pairs(names, mode="round_robin", symmetric=True)
        self.assertEqual(len(pairs), 3)
        self.assertCountEqual(pairs, [("a", "b"), ("a", "c"), ("b", "c")])

    def test_asymmetric_mode_yields_ordered_pairs(self) -> None:
        builder = TournamentBuilder()
        pairs = builder.pairs(["a", "b"], mode="round_robin", symmetric=False)
        # Both directions when symmetric=False.
        self.assertCountEqual(pairs, [("a", "b"), ("b", "a")])

    def test_unknown_mode_rejected(self) -> None:
        builder = TournamentBuilder()
        with self.assertRaises(ValueError):
            builder.pairs(["a", "b"], mode="bogus", symmetric=True)

    def test_pair_config_slices_agents_block(self) -> None:
        cfg = _config()
        cfg["agents"]["names"] = ["alice", "bob", "carol"]
        cfg["agents"]["personalities"]["en"] = ["nice", "mean", "shy"]
        cfg["agents"]["opponentPersonalityProb"] = [0, 50, 100]
        pair_cfg = TournamentBuilder().build_pair_config(cfg, ("bob", "carol"), pair_idx=0)
        self.assertEqual(pair_cfg["agents"]["names"], ["bob", "carol"])
        self.assertEqual(pair_cfg["agents"]["personalities"]["en"], ["mean", "shy"])

    def test_pair_config_slices_dict_llms_to_pair_only(self) -> None:
        cfg = _config()
        cfg.pop("llm")
        cfg["llms"] = {
            "a": "OpenAIGPT4o",
            "b": "Claude35Sonnet",
            "c": "MistralLarge",
        }
        cfg["agents"]["names"] = ["a", "b", "c"]
        cfg["agents"]["personalities"]["en"] = ["x", "y", "z"]
        cfg["agents"]["opponentPersonalityProb"] = [0, 0, 0]
        pair_cfg = TournamentBuilder().build_pair_config(cfg, ("a", "c"), 0)
        self.assertEqual(pair_cfg["llms"], {"a": "OpenAIGPT4o", "c": "MistralLarge"})


# ---------------------------------------------------------------------------
# Factory still works end-to-end
# ---------------------------------------------------------------------------

class TestFactoryStillWorks(unittest.TestCase):
    """The end-to-end factory flow must keep producing identical results
    after the collaborator extraction."""

    def test_create_games_uses_expander(self) -> None:
        from src.fairgame_factory import FairGameFactory

        factory = FairGameFactory()
        config = factory.io_manager.process_and_validate_configuration(
            {
                "name": "demo",
                "nRounds": 1,
                "nRoundsIsKnown": True,
                "languages": ["en"],
                "allAgentPermutations": True,
                "agents": {
                    "names": ["a", "b"],
                    "personalities": {"en": ["nice", "mean"]},
                    "opponentPersonalityProb": [0],
                },
                "llm": "OpenAIGPT4o",
                "promptTemplate": {"en": "{currentPlayerName} {choose}: [pick {strategy1}.]"},
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
            }
        )
        games = factory.create_games(config)
        # Symmetric dedup: 3 games for 2 personalities × 2 agents.
        self.assertEqual(len(games), 3)


if __name__ == "__main__":
    unittest.main()
