"""Regression tests for the bugs found during the post-refactor scan."""

from __future__ import annotations

import random
import unittest

from src.belief_parser import BeliefParseError, parse_belief
from src.fake_message_generator import FakeMessageGenerator
from src.io_managers.configuration_validator import ConfigValidator
from src.results_processing.agent_info import AgentInfo

STRATEGIES = {"strategy1": "Cooperate", "strategy2": "Defect"}


class TestFakeMessageGeneratorIsDeterministicWithRng(unittest.TestCase):
    """Bug 1: ``FakeMessageGenerator`` used the global ``random`` module so
    seeded runs were non-reproducible."""

    def test_same_rng_seed_produces_identical_output(self) -> None:
        a = FakeMessageGenerator(count=3, base="hex", rng=random.Random(7))
        b = FakeMessageGenerator(count=3, base="hex", rng=random.Random(7))
        self.assertEqual(
            [a.generate(None, i) for i in range(4)],
            [b.generate(None, i) for i in range(4)],
        )

    def test_different_seeds_diverge(self) -> None:
        a = FakeMessageGenerator(count=2, base="dec", rng=random.Random(1))
        b = FakeMessageGenerator(count=2, base="dec", rng=random.Random(2))
        self.assertNotEqual(a.generate(None, 0), b.generate(None, 0))


class TestBeliefParserBraceCounting(unittest.TestCase):
    """Bug 4: greedy regex over-matched when prose followed the JSON.

    Brace counting must extract only the first balanced object.
    """

    def test_handles_text_with_stray_brace_after_json(self) -> None:
        text = (
            "Here's my prediction: "
            '{"Cooperate": 0.7, "Defect": 0.3}'
            ". Hope this is helpful! Note: } stray brace."
        )
        result = parse_belief(text, STRATEGIES)
        self.assertAlmostEqual(result["strategy1"], 0.7)

    def test_unterminated_json_raises_clearly(self) -> None:
        with self.assertRaises(BeliefParseError):
            parse_belief('{"Cooperate": 0.5, "Defect": 0.5', STRATEGIES)


class TestAgentInfoCarriesNewFields(unittest.TestCase):
    """Bug 3: AgentInfo silently dropped agent_type and baseline_strategy
    so tournament/ToM analysis lost critical metadata."""

    def test_optional_fields_emitted_when_present(self) -> None:
        info = AgentInfo(
            name="x",
            llm_service="OpenAIGPT4o",
            personality="cooperative",
            opponent_prob=0.5,
            agent_type="trusting",
            baseline_strategy="tit_for_tat",
        )
        out = info.to_dict(prefix="agent1_")
        self.assertEqual(out["agent1_agent_type"], "trusting")
        self.assertEqual(out["agent1_baseline_strategy"], "tit_for_tat")

    def test_optional_fields_omitted_when_absent(self) -> None:
        info = AgentInfo(
            name="x",
            llm_service="OpenAIGPT4o",
            personality="cooperative",
            opponent_prob=0.5,
        )
        out = info.to_dict(prefix="agent1_")
        self.assertNotIn("agent1_agent_type", out)
        self.assertNotIn("agent1_baseline_strategy", out)


class TestOpponentProbsValidatedInPermutationsMode(unittest.TestCase):
    """Bug 6: ``opponentPersonalityProb`` was allowed to be missing/empty
    when ``allAgentPermutations: true``, but the factory then crashed."""

    BASE_CONFIG = {
        "name": "demo",
        "nRounds": 1,
        "nRoundsIsKnown": True,
        "llm": "OpenAIGPT4o",
        "languages": ["en"],
        "allAgentPermutations": True,
        "agents": {
            "names": ["a", "b"],
            "personalities": {"en": ["nice", "mean"]},
            # opponentPersonalityProb omitted on purpose
        },
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
        "templateFilename": "demo",
    }

    def test_missing_opponent_probs_now_rejected(self) -> None:
        with self.assertRaises(TypeError):
            ConfigValidator().validate_config_structure(self.BASE_CONFIG)

    def test_empty_opponent_probs_now_rejected(self) -> None:
        config = {
            **self.BASE_CONFIG,
            "agents": {**self.BASE_CONFIG["agents"], "opponentPersonalityProb": []},
        }
        with self.assertRaises(TypeError):
            ConfigValidator().validate_config_structure(config)

    def test_pool_of_one_value_accepted_when_permuting(self) -> None:
        config = {
            **self.BASE_CONFIG,
            "agents": {
                **self.BASE_CONFIG["agents"],
                "opponentPersonalityProb": [0],
            },
        }
        result = ConfigValidator().validate_config_structure(config)
        self.assertEqual(result["agents"]["opponentPersonalityProb"], [0])


if __name__ == "__main__":
    unittest.main()
