"""Tests for the new :class:`src.game_config.GameConfig` dataclass.

The dataclass bundles all the per-game parameters previously sprawled
across :class:`FairGame.__init__` and runs validation in one place.
"""

from __future__ import annotations

import unittest

from src.game_config import GameConfig
from src.utility import IdentityTransform, FehrSchmidtTransform


def _matrix_data() -> dict:
    return {
        "weights": {"w1": 1, "w2": 2},
        "strategies": {"en": {"strategy1": "A", "strategy2": "B"}},
        "combinations": {
            "c1": ["strategy1", "strategy1"],
            "c2": ["strategy2", "strategy2"],
        },
        "matrix": {"c1": ["w1", "w1"], "c2": ["w2", "w2"]},
    }


def _minimal_config(**overrides) -> GameConfig:
    base = dict(
        name="t",
        language="en",
        n_rounds=1,
        n_rounds_known=True,
        payoff_matrix_data=_matrix_data(),
        prompt_template="ignored",
        stop_conditions=[],
        agents_communicate=False,
    )
    base.update(overrides)
    return GameConfig(**base)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestGameConfigConstruction(unittest.TestCase):
    def test_minimal_config_constructs_with_defaults(self) -> None:
        cfg = _minimal_config()
        self.assertEqual(cfg.name, "t")
        self.assertEqual(cfg.discount_factor, 1.0)
        self.assertIsNone(cfg.continuation_probability)
        self.assertEqual(cfg.tom_order, 1)
        self.assertFalse(cfg.elicit_beliefs)
        self.assertFalse(cfg.mixed_strategies)
        self.assertTrue(cfg.reputation_applies)

    def test_default_utility_transform_is_identity(self) -> None:
        cfg = _minimal_config()
        self.assertIsInstance(cfg.utility_transform, IdentityTransform)

    def test_explicit_utility_transform_preserved(self) -> None:
        transform = FehrSchmidtTransform(alpha=0.4, beta=0.6)
        cfg = _minimal_config(utility_transform=transform)
        self.assertIs(cfg.utility_transform, transform)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestGameConfigValidation(unittest.TestCase):
    def test_discount_factor_zero_rejected(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _minimal_config(discount_factor=0.0)
        self.assertIn("discount", str(ctx.exception).lower())

    def test_discount_factor_above_one_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _minimal_config(discount_factor=1.5)

    def test_continuation_probability_zero_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _minimal_config(continuation_probability=0.0)

    def test_continuation_probability_above_one_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _minimal_config(continuation_probability=1.5)

    def test_tom_order_must_be_in_zero_to_two(self) -> None:
        # Currently the engine treats any int but the documented values are 0/1/2.
        # We don't enforce here; the prompt creator handles unknowns by treating
        # >=2 as second-order. Just verify in-range values are accepted.
        for k in (0, 1, 2):
            cfg = _minimal_config(tom_order=k)
            self.assertEqual(cfg.tom_order, k)


# ---------------------------------------------------------------------------
# FairGame integration
# ---------------------------------------------------------------------------

class TestFairGameAcceptsConfig(unittest.TestCase):
    """``FairGame.from_config(cfg, agents=...)`` must construct an equivalent
    game to passing the kwargs individually."""

    def _stub_agents(self) -> dict:
        from unit_tests.test_fairgame import _StubAgent

        return {"a1": _StubAgent("a1"), "a2": _StubAgent("a2")}

    def test_from_config_constructs_fairgame(self) -> None:
        from src.fairgame import FairGame

        cfg = _minimal_config(name="from-cfg")
        game = FairGame.from_config(cfg, agents=self._stub_agents())
        self.assertEqual(game.name, "from-cfg")
        self.assertEqual(game.n_rounds, 1)
        self.assertEqual(game.language, "en")

    def test_from_config_propagates_optional_fields(self) -> None:
        from src.fairgame import FairGame

        cfg = _minimal_config(
            discount_factor=0.9,
            continuation_probability=0.95,
            elicit_beliefs=True,
            tom_order=2,
            seed=42,
            reputation_applies=False,
        )
        game = FairGame.from_config(cfg, agents=self._stub_agents())
        self.assertAlmostEqual(game.discount_factor, 0.9)
        self.assertAlmostEqual(game.continuation_probability, 0.95)
        self.assertTrue(game.elicit_beliefs)
        self.assertEqual(game.tom_order, 2)
        self.assertEqual(game.seed, 42)
        self.assertFalse(game.reputation_applies)


if __name__ == "__main__":
    unittest.main()
