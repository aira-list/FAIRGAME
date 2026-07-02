"""End-to-end tests for the Theory-of-Mind features.

Covers:

* belief elicitation phase + history capture
* ToM-order ablation in rendered prompts
* private agent types drawn from a prior
* belief metrics flowing into the results DataFrame
"""

from __future__ import annotations

import unittest
from pathlib import Path

import pytest

from src.factory.fairgame_factory import FairGameFactory
from src.game.payoff_matrix import PayoffMatrix
from src.io_managers.io_manager import IoManager
from src.prompting.prompt_creator import PromptCreator
from src.results_processing.results_processor import ResultsProcessor
from src.utils.utils import get_resources_dir
from unit_tests.support import RESOURCES_SKIP_REASON, resources_available

# The ToM end-to-end tests load templates/configs from the sibling resources
# folder (not shipped with this repo) — skip cleanly when it's absent.
pytestmark = pytest.mark.skipif(not resources_available(), reason=RESOURCES_SKIP_REASON)

BASE_DIR = Path(__file__).resolve().parent
RESOURCES_PATH = get_resources_dir()


def _payoff_matrix_data() -> dict:
    return {
        "weights": {"weight1": 6, "weight2": 10, "weight3": 0, "weight4": 2},
        "strategies": {
            "en": {"strategy1": "Cooperate", "strategy2": "Defect"},
        },
        "combinations": {
            "c1": ["strategy1", "strategy1"],
            "c2": ["strategy1", "strategy2"],
            "c3": ["strategy2", "strategy1"],
            "c4": ["strategy2", "strategy2"],
        },
        "matrix": {
            "c1": ["weight1", "weight1"],
            "c2": ["weight3", "weight2"],
            "c3": ["weight2", "weight3"],
            "c4": ["weight4", "weight4"],
        },
    }


class _StubAgent:
    def __init__(self, name: str, personality: str = "cooperative", prob: float = 50) -> None:
        self.name = name
        self.personality = personality
        self.opponent_personality_prob = prob
        self.agent_type = None


class TestPromptCreatorToMOrder(unittest.TestCase):
    """ToM order ablation must visibly change rendered prompts."""

    TEMPLATE = (
        "You are {currentPlayerName} and your opponent is {opponent1}.\n"
        "{intro}: [You are {personality}.]\n"
        "{opponentIntro}: [{opponent1} has a probability of {opponentPersonalityProbability1}% of being {opponentPersonality1}.]\n"
        "{secondOrder}: [Remember that {opponent1} is also reasoning about you.]\n"
        "{choose}: [Choose between {strategy1} and {strategy2}.]"
    )

    def _render(self, tom_order: int) -> str:
        pm = PayoffMatrix(_payoff_matrix_data(), "en")
        creator = PromptCreator(
            "en",
            self.TEMPLATE,
            n_rounds=1,
            n_rounds_known=False,
            payoff_matrix=pm,
            tom_order=tom_order,
        )
        agent = _StubAgent("agent1")
        opp = _StubAgent("agent2", personality="selfish", prob=80)
        return creator.fill_template(agent, [opp], current_round=1, history={}, phase="choose")

    def test_order_zero_strips_opponent_information(self) -> None:
        prompt = self._render(tom_order=0)
        self.assertNotIn("probability", prompt)
        self.assertNotIn("reasoning about", prompt)

    def test_order_one_shows_opponent_but_not_second_order(self) -> None:
        prompt = self._render(tom_order=1)
        self.assertIn("probability of 80%", prompt)
        self.assertNotIn("reasoning about", prompt)

    def test_order_two_includes_second_order_block(self) -> None:
        prompt = self._render(tom_order=2)
        self.assertIn("probability of 80%", prompt)
        self.assertIn("reasoning about", prompt)


class TestBeliefPhaseEndToEnd(unittest.TestCase):
    """A run with elicitBeliefs records a belief per agent per round."""

    def setUp(self) -> None:
        self.io_manager = IoManager(root_path=str(RESOURCES_PATH))
        self.factory = FairGameFactory()
        self.factory.set_io_manager(self.io_manager)

    def test_belief_recorded_in_history(self) -> None:
        results = self.factory.load_config_create_and_run_games(
            "prisoner_dilemma_tom/prisoner_dilemma_tom.json"
        )
        history = results["game_0"]["history"]
        self.assertGreater(len(history), 0)
        for round_entries in history.values():
            for entry in round_entries:
                self.assertIn("belief", entry, msg="believe phase did not record")
                self.assertIsNotNone(entry["belief"])
                self.assertAlmostEqual(sum(entry["belief"].values()), 1.0, places=4)

    def test_description_carries_tom_metadata(self) -> None:
        results = self.factory.load_config_create_and_run_games(
            "prisoner_dilemma_tom/prisoner_dilemma_tom.json"
        )
        desc = results["game_0"]["description"]
        self.assertTrue(desc["elicit_beliefs"])
        self.assertEqual(desc["tom_order"], 2)
        self.assertIn("types", desc)


class TestPrivateTypesAreAssigned(unittest.TestCase):
    def test_each_agent_gets_a_type_from_the_prior(self) -> None:
        io_manager = IoManager(root_path=str(RESOURCES_PATH))
        factory = FairGameFactory()
        factory.set_io_manager(io_manager)
        config = factory.load_config("prisoner_dilemma_tom/prisoner_dilemma_tom.json")
        config = io_manager.process_and_validate_configuration(config)
        factory.create_games(config)

        labels = set(config["agents"]["types"]["labels"])
        for game in factory.games:
            for agent in game.agents.values():
                self.assertIn(agent.agent_type, labels)


class TestResultsProcessorEmitsBeliefMetrics(unittest.TestCase):
    def test_dataframe_includes_brier_columns(self) -> None:
        io_manager = IoManager(root_path=str(RESOURCES_PATH))
        factory = FairGameFactory()
        factory.set_io_manager(io_manager)
        results = factory.load_config_create_and_run_games(
            "prisoner_dilemma_tom/prisoner_dilemma_tom.json"
        )
        df = ResultsProcessor().process(results)
        self.assertIn("agent1_belief_mean_brier", df.columns)
        self.assertIn("agent2_belief_mean_brier", df.columns)
        self.assertIsNotNone(df.iloc[0]["agent1_belief_mean_brier"])
        self.assertIsNotNone(df.iloc[0]["agent2_belief_mean_brier"])


# ---------------------------------------------------------------------------
# Invariants and determinism
# ---------------------------------------------------------------------------


class TestBriefScoreInvariants(unittest.TestCase):
    """Properties that must hold for every emitted Brier score."""

    def setUp(self) -> None:
        self.io_manager = IoManager(root_path=str(RESOURCES_PATH))
        self.factory = FairGameFactory()
        self.factory.set_io_manager(self.io_manager)

    def test_brier_columns_within_zero_two(self) -> None:
        results = self.factory.load_config_create_and_run_games(
            "prisoner_dilemma_tom/prisoner_dilemma_tom.json"
        )
        df = ResultsProcessor().process(results)
        for col in ("agent1_belief_mean_brier", "agent2_belief_mean_brier"):
            value = df.iloc[0][col]
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 2.0)

    def test_p_outcome_columns_within_zero_one(self) -> None:
        results = self.factory.load_config_create_and_run_games(
            "prisoner_dilemma_tom/prisoner_dilemma_tom.json"
        )
        df = ResultsProcessor().process(results)
        for col in ("agent1_belief_mean_p_outcome", "agent2_belief_mean_p_outcome"):
            value = df.iloc[0][col]
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 1.0)


class TestDeterminism(unittest.TestCase):
    def test_same_seed_yields_same_type_draws(self) -> None:
        # Add a seed and run twice — type assignment must match.
        io_manager = IoManager(root_path=str(RESOURCES_PATH))

        def _types() -> list:
            factory = FairGameFactory()
            factory.set_io_manager(io_manager)
            config = factory.load_config("prisoner_dilemma_tom/prisoner_dilemma_tom.json")
            config["seed"] = 42
            config = io_manager.process_and_validate_configuration(config)
            factory.create_games(config, resolved_seed=42)
            return [[agent.agent_type for agent in game.agents.values()] for game in factory.games]

        self.assertEqual(_types(), _types())


class TestBeliefMetricsAbsentWhenNotElicited(unittest.TestCase):
    def test_no_brier_columns_for_non_belief_run(self) -> None:
        # Plain PD config has elicit_beliefs unset → no belief columns.
        io_manager = IoManager(root_path=str(RESOURCES_PATH))
        factory = FairGameFactory()
        factory.set_io_manager(io_manager)
        results = factory.load_config_create_and_run_games(
            "prisoner_dilemma/prisoner_dilemma_round_known_conventional.json"
        )
        df = ResultsProcessor().process(results)
        self.assertNotIn("agent1_belief_mean_brier", df.columns)


if __name__ == "__main__":
    unittest.main()
