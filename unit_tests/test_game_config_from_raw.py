"""Deepening #1 — input-config shape knowledge lives in one module.

The factory used to read ~20 raw input-dict keys inline (``config["name"]``,
``bool(config.get("elicitBeliefs", False))``, …) to build a ``GameConfig``.
``GameConfig.from_raw`` concentrates that input-shape knowledge — keys,
defaults, and coercions — behind one interface.
"""

from __future__ import annotations

import random
import unittest

from src.game_config import GameConfig
from src.utility import IdentityTransform


def _minimal_raw() -> dict:
    return {
        "name": "demo",
        "nRounds": 3,
        "nRoundsIsKnown": True,
        "stopGameWhen": [],
        "agentsCommunicate": False,
    }


class TestGameConfigFromRaw(unittest.TestCase):
    def _build(self, raw):
        return GameConfig.from_raw(
            raw,
            language="en",
            payoff_matrix_data={"strategies": {}},
            prompt_template="T",
            types_config=None,
            rng=random.Random(1),
            seed=1,
        )

    def test_required_fields_mapped(self) -> None:
        cfg = self._build(_minimal_raw())
        self.assertEqual(cfg.name, "demo")
        self.assertEqual(cfg.n_rounds, 3)
        self.assertTrue(cfg.n_rounds_known)
        self.assertEqual(cfg.language, "en")

    def test_optional_defaults_applied(self) -> None:
        cfg = self._build(_minimal_raw())
        self.assertFalse(cfg.elicit_beliefs)
        self.assertEqual(cfg.tom_order, 1)
        self.assertEqual(cfg.discount_factor, 1.0)
        self.assertTrue(cfg.reputation_applies)
        self.assertIsInstance(cfg.utility_transform, IdentityTransform)
        self.assertEqual(list(cfg.equilibria), [])

    def test_coercions_and_overrides(self) -> None:
        raw = _minimal_raw()
        raw.update(
            {
                "elicitBeliefs": 1,  # truthy -> True
                "tomOrder": "2",  # str -> int
                "discountFactor": "0.9",  # str -> float
                "reputationApplies": 0,  # falsy -> False
                "payoffVariantName": "harsh",
            }
        )
        cfg = self._build(raw)
        self.assertIs(cfg.elicit_beliefs, True)
        self.assertEqual(cfg.tom_order, 2)
        self.assertEqual(cfg.discount_factor, 0.9)
        self.assertIs(cfg.reputation_applies, False)
        self.assertEqual(cfg.payoff_variant_name, "harsh")


if __name__ == "__main__":
    unittest.main()
