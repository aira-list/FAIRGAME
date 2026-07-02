"""Tests for the polymorphic Agent hierarchy."""

from __future__ import annotations

import unittest
from unittest import mock

from src.agent import Agent, BaselineAgent, LLMAgent
from src.baseline_strategies import AlwaysCooperate

# ---------------------------------------------------------------------------
# Hierarchy
# ---------------------------------------------------------------------------


class TestHierarchy(unittest.TestCase):
    def test_llm_agent_is_an_agent(self) -> None:
        a = LLMAgent("a", "OpenAIGPT4o", "neutral", 0.5)
        self.assertIsInstance(a, Agent)

    def test_baseline_agent_is_an_agent(self) -> None:
        a = BaselineAgent("a", AlwaysCooperate(), "neutral", 0.0)
        self.assertIsInstance(a, Agent)

    def test_llm_and_baseline_share_no_subclass_relation(self) -> None:
        # Both inherit from Agent but neither is a subclass of the other.
        self.assertFalse(issubclass(LLMAgent, BaselineAgent))
        self.assertFalse(issubclass(BaselineAgent, LLMAgent))


# ---------------------------------------------------------------------------
# LLMAgent behaviour
# ---------------------------------------------------------------------------


class TestLLMAgent(unittest.TestCase):
    def test_calls_execute_prompt_with_llm_service_and_prompt(self) -> None:
        agent = LLMAgent("agent1", "OpenAIGPT4o", "neutral", 0.0)
        with mock.patch("src.agent.execute_prompt", return_value="ok") as mock_exec:
            response = agent.execute_round("hello")
        self.assertEqual(response, "ok")
        mock_exec.assert_called_once_with("OpenAIGPT4o", "hello")

    def test_get_info_includes_llm_service(self) -> None:
        agent = LLMAgent("agent1", "OpenAIGPT4o", "selfish", 70)
        info = agent.get_info()
        self.assertEqual(info["name"], "agent1")
        self.assertEqual(info["llm_service"], "OpenAIGPT4o")
        self.assertEqual(info["personality"], "selfish")
        self.assertEqual(info["opponent_personality_probability"], 70)


# ---------------------------------------------------------------------------
# BaselineAgent behaviour
# ---------------------------------------------------------------------------


class TestBaselineAgent(unittest.TestCase):
    def test_get_info_includes_baseline_strategy_name(self) -> None:
        agent = BaselineAgent("a", AlwaysCooperate(), "n/a", 0)
        info = agent.get_info()
        self.assertEqual(info["baseline_strategy"], "always_cooperate")

    def test_baseline_agent_is_callable_via_strategy_choose(self) -> None:
        # The baseline doesn't go through execute_round; the round runner
        # calls strategy.choose(agent, game, round_number).
        agent = BaselineAgent("a", AlwaysCooperate(), "n/a", 0)
        self.assertIs(type(agent.baseline_strategy), AlwaysCooperate)

    def test_execute_round_should_not_be_used_for_baseline_agents(self) -> None:
        # Calling execute_round on a baseline agent is a programming error;
        # the engine routes baselines through the strategy directly.
        agent = BaselineAgent("a", AlwaysCooperate(), "n/a", 0)
        with self.assertRaises(NotImplementedError):
            agent.execute_round("anything")


# ---------------------------------------------------------------------------
# Explicit construction contract
# ---------------------------------------------------------------------------


class TestExplicitConstruction(unittest.TestCase):
    def test_agent_base_class_is_abstract(self) -> None:
        # No dispatch magic: Agent is an ABC and cannot be instantiated —
        # callers pick LLMAgent or BaselineAgent explicitly.
        with self.assertRaises(TypeError):
            Agent("a1", "OpenAIGPT4o", "neutral", 0.5)

    def test_baseline_agent_derives_llm_service_from_strategy(self) -> None:
        a = BaselineAgent("a1", AlwaysCooperate(), "n/a", 0)
        self.assertEqual(a.llm_service, "Baseline:always_cooperate")

    def test_baseline_agent_llm_service_override_preserved(self) -> None:
        # The factory passes the user's exact model id so results columns
        # show what the config said.
        a = BaselineAgent("a1", AlwaysCooperate(), "n/a", 0, llm_service="baseline:AlwaysCooperate")
        self.assertEqual(a.llm_service, "baseline:AlwaysCooperate")
        self.assertIs(a.baseline_strategy.__class__, AlwaysCooperate)


if __name__ == "__main__":
    unittest.main()
