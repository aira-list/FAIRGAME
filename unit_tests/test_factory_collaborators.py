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


def _asymmetric_matrix() -> dict:
    """Battle-of-the-Sexes-shaped matrix: coordination cells favour one player."""
    return {
        "weights": {"w_hi": 10, "w_lo": 7, "w_zero": 0},
        "strategies": {"en": {"strategy1": "Opera", "strategy2": "Football"}},
        "combinations": {
            "combination1": ["strategy1", "strategy1"],
            "combination2": ["strategy1", "strategy2"],
            "combination3": ["strategy2", "strategy1"],
            "combination4": ["strategy2", "strategy2"],
        },
        "matrix": {
            "combination1": ["w_hi", "w_lo"],
            "combination2": ["w_zero", "w_zero"],
            "combination3": ["w_zero", "w_zero"],
            "combination4": ["w_lo", "w_hi"],
        },
    }


class TestPermutationExpanderDuplicatePools(unittest.TestCase):
    def test_duplicate_pool_values_do_not_duplicate_games(self) -> None:
        # A 1:1-style config (every agent "neutral", every prior 0) under
        # allAgentPermutations must produce ONE game, not 10 copies.
        cfg = _config()
        cfg["agents"]["personalities"]["en"] = ["neutral", "neutral"]
        cfg["agents"]["opponentPersonalityProb"] = [0, 0]
        df = PermutationExpander().expand(cfg, language="en")
        self.assertEqual(len(df), 1)
        self.assertEqual(len(df.drop_duplicates()), len(df))

    def test_duplicate_pool_values_deduped_with_mixed_llms(self) -> None:
        cfg = _config()
        cfg.pop("llm")
        cfg["llms"] = {"a": "OpenAIGPT4o", "b": "Claude35Sonnet"}
        cfg["agents"]["personalities"]["en"] = ["nice", "nice", "mean"]
        df = PermutationExpander().expand(cfg, language="en")
        # Unique joint values: {nice, mean} x {0} per agent -> 2^2 ordered rows.
        self.assertEqual(len(df), 4)


class TestPermutationExpanderPositionSensitivity(unittest.TestCase):
    """Symmetric collapse must only fire when position truly doesn't matter."""

    def test_no_collapse_when_payoff_matrix_is_asymmetric(self) -> None:
        cfg = _config(payoffMatrix=_asymmetric_matrix())
        df = PermutationExpander().expand(cfg, language="en")
        # Same LLM, but the matrix favours positions: both orderings needed.
        self.assertEqual(len(df), 4)
        pairs = set(zip(df["Personality1"], df["Personality2"], strict=True))
        self.assertIn(("nice", "mean"), pairs)
        self.assertIn(("mean", "nice"), pairs)

    def test_no_collapse_when_agents_communicate(self) -> None:
        # Messages are written sequentially in agent order, so the second
        # speaker conditions on the first: position matters.
        cfg = _config(agentsCommunicate=True)
        df = PermutationExpander().expand(cfg, language="en")
        self.assertEqual(len(df), 4)

    def test_collapse_kept_for_symmetric_matrix_without_communication(self) -> None:
        symmetric = _asymmetric_matrix()
        symmetric["matrix"]["combination1"] = ["w_hi", "w_hi"]
        symmetric["matrix"]["combination4"] = ["w_lo", "w_lo"]
        cfg = _config(payoffMatrix=symmetric)
        df = PermutationExpander().expand(cfg, language="en")
        self.assertEqual(len(df), 3)


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
        # 1:1 mode: personality i belongs to agent i, so the pair keeps
        # exactly its own two entries.
        cfg = _config(allAgentPermutations=False)
        cfg["agents"]["names"] = ["alice", "bob", "carol"]
        cfg["agents"]["personalities"]["en"] = ["nice", "mean", "shy"]
        cfg["agents"]["opponentPersonalityProb"] = [0, 50, 100]
        pair_cfg, _ = TournamentBuilder().build_pair_config(cfg, ("bob", "carol"), pair_idx=0)
        self.assertEqual(pair_cfg["agents"]["names"], ["bob", "carol"])
        self.assertEqual(pair_cfg["agents"]["personalities"]["en"], ["mean", "shy"])
        self.assertEqual(pair_cfg["agents"]["opponentPersonalityProb"], [50, 100])

    def test_pair_config_keeps_full_pools_under_all_permutations(self) -> None:
        # Pool mode: personalities/priors are conditions to permute over, not
        # per-agent attributes — every pair must see the WHOLE pool (slicing
        # positionally silently dropped "shy" games for the (alice, bob) pair
        # and crashed when the pool was shorter than the roster).
        cfg = _config(allAgentPermutations=True)
        cfg["agents"]["names"] = ["alice", "bob", "carol"]
        cfg["agents"]["personalities"]["en"] = ["nice", "mean", "shy"]
        cfg["agents"]["opponentPersonalityProb"] = [0, 50]
        pair_cfg, _ = TournamentBuilder().build_pair_config(cfg, ("alice", "bob"), pair_idx=0)
        self.assertEqual(pair_cfg["agents"]["names"], ["alice", "bob"])
        self.assertEqual(pair_cfg["agents"]["personalities"]["en"], ["nice", "mean", "shy"])
        self.assertEqual(pair_cfg["agents"]["opponentPersonalityProb"], [0, 50])

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
        pair_cfg, _ = TournamentBuilder().build_pair_config(cfg, ("a", "c"), 0)
        self.assertEqual(pair_cfg["llms"], {"a": "OpenAIGPT4o", "c": "MistralLarge"})


# ---------------------------------------------------------------------------
# Factory still works end-to-end
# ---------------------------------------------------------------------------


class TestFactoryStillWorks(unittest.TestCase):
    """The end-to-end factory flow must keep producing identical results
    after the collaborator extraction."""

    def test_create_games_uses_expander(self) -> None:
        from src.factory.fairgame_factory import FairGameFactory

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
