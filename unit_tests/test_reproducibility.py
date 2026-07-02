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
