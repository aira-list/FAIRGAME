"""Demo mode: run LLM scenarios with zero API keys.

The README/GUI advertise a demo mode that answers every LLM call with a fast,
deterministic in-process fake so the app is explorable without provider keys.
These tests pin that contract:

* inside ``demo_mode()`` the factory hands back a ``DemoConnector`` (never the
  live LiteLLM connector), for any model name;
* the run endpoints default to demo mode, so an LLM config runs and persists
  rows without any key configured.
"""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from src.llm_connectors import ChatModelFactory, demo_mode
from src.llm_connectors.demo_connector import DemoConnector
from src.llm_connectors.litellm_connector import LiteLLMConnector


class TestDemoConnectorSelection(unittest.TestCase):
    def test_demo_mode_returns_demo_connector(self) -> None:
        # "GPT-4o" is a featured model with no test override, so outside demo
        # it resolves to the live LiteLLM connector.
        self.assertIsInstance(ChatModelFactory.get_model("GPT-4o"), LiteLLMConnector)
        with demo_mode():
            self.assertIsInstance(ChatModelFactory.get_model("GPT-4o"), DemoConnector)
        # Registry restored on exit.
        self.assertIsInstance(ChatModelFactory.get_model("GPT-4o"), LiteLLMConnector)

    def test_demo_mode_handles_arbitrary_litellm_names(self) -> None:
        with demo_mode():
            conn = ChatModelFactory.get_model("litellm:some/unregistered-model")
            self.assertIsInstance(conn, DemoConnector)

    def test_demo_connector_answers_a_choice_prompt_offline(self) -> None:
        conn = DemoConnector("anything")
        reply = conn.send_prompt("Choose between Cooperate and Betray.")
        self.assertIn(reply, {"Cooperate", "Betray"})


class TestRunEndpointsDefaultToDemo(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from unit_tests.support import isolated_storage_dirs
        from web_api.main import app

        cls._dirs_cm = isolated_storage_dirs(prefix="fg_demo_")
        cls._dirs_cm.__enter__()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._dirs_cm.__exit__(None, None, None)

    # Shipped LLM seed configs use "GPT-4o" / "Claude Sonnet 4.6" — neither is
    # a test-fake-overridden model, so they hit the live connector unless demo
    # mode is active. A passing run therefore proves demo is on by default.
    def test_llm_seed_config_runs_offline_by_default(self) -> None:
        res = self.client.post("/api/configurations/seed_cfg_pd_llm/run")
        self.assertEqual(res.status_code, 200, res.text)
        self.assertTrue(res.json()["rows"])

    def test_theory_of_mind_seed_config_runs_offline(self) -> None:
        # pd_tom exercises the belief-elicitation path; confirm it runs end to
        # end in the shipped app under demo mode (no external resources needed).
        res = self.client.post("/api/configurations/seed_cfg_pd_tom/run")
        self.assertEqual(res.status_code, 200, res.text)
        self.assertTrue(res.json()["rows"])


if __name__ == "__main__":
    unittest.main()
