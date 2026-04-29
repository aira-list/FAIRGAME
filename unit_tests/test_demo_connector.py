"""Tests for the demo-mode connector swap (``src.demo_connector``).

The demo connector replaces the real LLM provider registry with a
deterministic stub so the CLI / FastAPI / pytest harness can run
end-to-end without paid API keys. Toggling the demo mode is supposed
to be:

* *idempotent* — calling ``set_demo_mode(True)`` twice is the same as
  once;
* *reversible* — calling it with ``False`` restores the original
  registry exactly as it was at import time;
* *honest* — the swap rewrites the global ``MODEL_PROVIDER_MAP`` so
  any code path going through ``execute_prompt`` actually hits the
  stub (no separate "demo branch" to drift out of sync).
"""

from __future__ import annotations

import json
import unittest

from src import demo_connector
from src.llm_connectors import llm_factory_connector


class TestDemoConnectorSwap(unittest.TestCase):
    """The demo connector must install/restore cleanly."""

    def setUp(self) -> None:
        # Always start from a known clean state.
        demo_connector.restore_real_connectors()

    def tearDown(self) -> None:
        demo_connector.restore_real_connectors()

    def test_install_swaps_registry(self) -> None:
        snapshot_before = dict(llm_factory_connector.MODEL_PROVIDER_MAP)
        demo_connector.install_demo_connector()
        # Every entry in _TARGET_MODELS now points at the demo provider
        # tag. Registry values are ``(loader_callable, provider_name)``
        # tuples — the provider name is what marks an entry as "demo".
        self.assertTrue(demo_connector.is_demo_active())
        for name in demo_connector._TARGET_MODELS:
            entry = llm_factory_connector.MODEL_PROVIDER_MAP.get(name)
            self.assertIsNotNone(entry, f"{name!r} missing from registry after install")
            self.assertEqual(entry[1], "demo")
        # The original snapshot was non-empty (sanity).
        self.assertGreater(len(snapshot_before), 0)

    def test_restore_clears_demo_flag(self) -> None:
        snapshot_before = dict(llm_factory_connector.MODEL_PROVIDER_MAP)
        demo_connector.install_demo_connector()
        demo_connector.restore_real_connectors()
        self.assertFalse(demo_connector.is_demo_active())
        # The post-restore registry must equal the pre-install snapshot.
        self.assertEqual(
            llm_factory_connector.MODEL_PROVIDER_MAP, snapshot_before,
            "Restore did not roll back to the pre-install registry.",
        )

    def test_set_demo_mode_idempotent(self) -> None:
        demo_connector.set_demo_mode(True)
        demo_connector.set_demo_mode(True)
        self.assertTrue(demo_connector.is_demo_active())
        demo_connector.set_demo_mode(False)
        demo_connector.set_demo_mode(False)
        self.assertFalse(demo_connector.is_demo_active())


class TestDemoConnectorBehaviour(unittest.TestCase):
    def test_belief_prompt_returns_valid_json(self) -> None:
        # When the prompt looks like a belief-elicitation request, the
        # demo connector must return a JSON probability map — this
        # keeps the engine's belief parser path exercisable in demo.
        connector = demo_connector._DemoConnector()
        response = connector._send_prompt(
            'Predict probability of Cooperate vs Defect. Reply with JSON.'
        )
        parsed = json.loads(response)
        self.assertIsInstance(parsed, dict)
        # Probabilities are non-negative and finite.
        for v in parsed.values():
            self.assertGreaterEqual(v, 0.0)
            self.assertLess(v, 1.5)  # may sum > 1 by design; checked elsewhere

    def test_choice_prompt_returns_first_known_label(self) -> None:
        connector = demo_connector._DemoConnector()
        # "between Cooperate and Defect" → returns "Cooperate".
        response = connector._send_prompt(
            "Choose between Cooperate and Defect."
        )
        self.assertEqual(response, "Cooperate")

    def test_unknown_prompt_falls_back_to_first_label(self) -> None:
        connector = demo_connector._DemoConnector()
        response = connector._send_prompt("nothing recognisable here.")
        self.assertEqual(response, connector.KNOWN_LABELS[0])


if __name__ == "__main__":
    unittest.main()
