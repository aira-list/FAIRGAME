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
# Backward compatibility: the legacy ``Agent(...)`` factory still works.
# ---------------------------------------------------------------------------

class TestLegacyConstructor(unittest.TestCase):
    def test_legacy_agent_call_returns_llm_agent_when_no_baseline(self) -> None:
        # Pre-refactor code: Agent("a1", "OpenAIGPT4o", "neutral", 0.5)
        # Should still work and produce an LLM-driven agent.
        a = Agent("a1", "OpenAIGPT4o", "neutral", 0.5)
        self.assertIsInstance(a, LLMAgent)

    def test_legacy_agent_call_returns_baseline_agent_when_baseline_set(self) -> None:
        a = Agent(
            "a1",
            "Baseline:AlwaysCooperate",
            "n/a",
            0,
            baseline_strategy=AlwaysCooperate(),
        )
        self.assertIsInstance(a, BaselineAgent)

    def test_agent_keyword_form_with_baseline_strategy(self) -> None:
        # Some call sites build agents purely via kwargs (matches the
        # Agent.__init__ signature); this must dispatch to BaselineAgent
        # and not raise a TypeError on the renamed positional in
        # BaselineAgent.__init__.
        a = Agent(
            name="a1",
            llm_service="dummy",
            personality="neutral",
            opponent_personality_prob=0.0,
            baseline_strategy=AlwaysCooperate(),
        )
        self.assertIsInstance(a, BaselineAgent)
        self.assertEqual(a.name, "a1")
        self.assertEqual(a.personality, "neutral")
        # llm_service was provided explicitly — preserve it rather than
        # auto-deriving "Baseline:AlwaysCooperate".
        self.assertEqual(a.llm_service, "dummy")
        self.assertIs(a.baseline_strategy.__class__, AlwaysCooperate)


if __name__ == "__main__":
    unittest.main()
