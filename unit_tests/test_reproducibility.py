"""Phase 4 — reproducibility / seeding regression tests."""

from __future__ import annotations

import random
import unittest

from src.factory import PermutationExpander, TournamentBuilder
from src.utils.rng import combine_seed


class TestCombineSeed(unittest.TestCase):
    def test_axes_do_not_collide(self) -> None:
        # The old additive scheme collided: (10,1) == (11,0) == 11.
        self.assertNotEqual(combine_seed(10, 1), combine_seed(11, 0))

    def test_deterministic_and_32bit(self) -> None:
        self.assertEqual(combine_seed(42, 3), combine_seed(42, 3))
        self.assertTrue(0 <= combine_seed(42, 3) < 2**32)


class TestTournamentSeedNonCollision(unittest.TestCase):
    def _cfg(self) -> dict:
        return {
            "agents": {
                "names": ["a", "b", "c"],
                "personalities": {"en": ["x", "y", "z"]},
                "opponentPersonalityProb": [0, 0, 0],
            },
            "llm": "OpenAIGPT4o",
        }

    def test_distinct_seed_pair_cells_differ(self) -> None:
        b = TournamentBuilder()
        # (base 10, pair 1) and (base 11, pair 0) must NOT map to the same seed.
        _, s1 = b.build_pair_config(self._cfg(), ("a", "b"), pair_idx=1, resolved_seed=10)
        _, s2 = b.build_pair_config(self._cfg(), ("a", "b"), pair_idx=0, resolved_seed=11)
        self.assertNotEqual(s1, s2)


class TestPermutationRowRngDecorrelation(unittest.TestCase):
    """Games built in one permutation pass must not share one RNG stream.

    With an identically-seeded RNG per row, RandomChoice baselines, mixed
    sampling and continuation checks were perfectly correlated across the
    sweep's cells, biasing any variance computed over them. Same-seed
    reruns must stay byte-identical (reproducibility is per seed, not per
    process).
    """

    N_ROUNDS = 12

    def _cfg(self) -> dict:
        return {
            "name": "rng_demo",
            "nRounds": self.N_ROUNDS,
            "nRoundsIsKnown": True,
            "languages": ["en"],
            "allAgentPermutations": True,
            "agents": {
                "names": ["a", "b"],
                "personalities": {"en": ["nice", "mean"]},
                "opponentPersonalityProb": [0],
            },
            "llms": ["Baseline:Random", "Baseline:Random"],
            "promptTemplate": {"en": "(baseline game; never read)"},
            "payoffMatrix": {
                "weights": {"w1": 6, "w2": 10, "w3": 0, "w4": 2},
                "strategies": {"en": {"strategy1": "C", "strategy2": "D"}},
                "combinations": {
                    "combination1": ["strategy1", "strategy1"],
                    "combination2": ["strategy1", "strategy2"],
                    "combination3": ["strategy2", "strategy1"],
                    "combination4": ["strategy2", "strategy2"],
                },
                "matrix": {
                    "combination1": ["w1", "w1"],
                    "combination2": ["w3", "w2"],
                    "combination3": ["w2", "w3"],
                    "combination4": ["w4", "w4"],
                },
            },
            "stopGameWhen": [],
            "agentsCommunicate": False,
            "seed": 42,
        }

    @staticmethod
    def _strategy_streams(output: dict) -> list[tuple]:
        streams = []
        for game in output.values():
            per_agent: dict[str, list] = {}
            for round_rows in game["history"].values():
                for row in round_rows:
                    per_agent.setdefault(row["agent"], []).append(row["strategy"])
            streams.append(tuple(tuple(v) for v in per_agent.values()))
        return streams

    def test_rows_in_one_pass_draw_different_streams(self) -> None:
        from src.factory.fairgame_factory import FairGameFactory

        output = FairGameFactory().create_and_run_games(self._cfg())
        streams = self._strategy_streams(output)
        self.assertGreater(len(streams), 1)
        # With a shared stream every game's 2x12 random draws were identical;
        # decorrelated streams collide with probability 2^-24 per pair.
        self.assertGreater(len(set(streams)), 1)

    def test_same_seed_rerun_is_identical(self) -> None:
        from src.factory.fairgame_factory import FairGameFactory

        first = FairGameFactory().create_and_run_games(self._cfg())
        second = FairGameFactory().create_and_run_games(self._cfg())
        self.assertEqual(self._strategy_streams(first), self._strategy_streams(second))


class TestPermutationJointAxis(unittest.TestCase):
    def _cfg(self) -> dict:
        return {
            "name": "demo",
            "nRounds": 1,
            "nRoundsIsKnown": True,
            "languages": ["en"],
            "agents": {
                "names": ["a", "b"],
                "personalities": {"en": ["nice", "mean"]},
                "opponentPersonalityProb": [0, 1],
            },
            "llm": "OpenAIGPT4o",
            "allAgentPermutations": True,
        }

    def test_joint_assignments_not_dropped(self) -> None:
        df = PermutationExpander().expand(self._cfg(), language="en")
        # 4 joint per-agent attrs, 2 agents, shared LLM →
        # combinations_with_replacement(4, 2) = 10 (old buggy scheme: 9).
        self.assertEqual(len(df), 10)

    def test_crossed_joint_pairing_present(self) -> None:
        df = PermutationExpander().expand(self._cfg(), language="en")
        # A "crossed" assignment (different personality AND different prior per
        # agent) that independent-axis reduction would have dropped.
        crossed = df[
            (df["Personality1"] == "nice")
            & (df["OpponentPersonalityProb1"] == 0)
            & (df["Personality2"] == "mean")
            & (df["OpponentPersonalityProb2"] == 1)
        ]
        self.assertGreaterEqual(len(crossed), 1)


class TestAssignAgentTypesRequiresRng(unittest.TestCase):
    def test_rng_is_required(self) -> None:
        from src.factory.fairgame_factory import FairGameFactory

        with self.assertRaises(TypeError):
            # Missing the now-required rng argument.
            FairGameFactory._assign_agent_types({}, {"labels": ["x"], "probs": [1]})

    def test_seeded_assignment_is_deterministic(self) -> None:
        from src.agents.agent import LLMAgent
        from src.factory.fairgame_factory import FairGameFactory

        def assign(seed: int) -> list:
            agents = {
                n: LLMAgent(
                    name=n,
                    llm_service="OpenAIGPT4o",
                    personality="p",
                    opponent_personality_prob=0.5,
                )
                for n in ("a", "b", "c")
            }
            FairGameFactory._assign_agent_types(
                agents,
                {"labels": ["L1", "L2"], "probs": [0.5, 0.5]},
                random.Random(seed),
            )
            return [agents[n].agent_type for n in ("a", "b", "c")]

        self.assertEqual(assign(7), assign(7))


if __name__ == "__main__":
    unittest.main()
