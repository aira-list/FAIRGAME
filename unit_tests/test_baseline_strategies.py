"""Tests for :mod:`src.baseline_strategies`."""

from __future__ import annotations

import random
import unittest

from src.baseline_strategies import (
    AlwaysCooperate,
    AlwaysDefect,
    BASELINE_PREFIX,
    GrimTrigger,
    RandomChoice,
    RandomMixed,
    TitForTat,
    is_baseline_id,
    make_baseline,
    parse_baseline_id,
)


class _StubGame:
    def __init__(self) -> None:
        self.payoff_matrix = type(
            "PM", (), {"strategies": {"strategy1": "Cooperate", "strategy2": "Defect"}}
        )()
        self.agents: dict[str, _StubAgent] = {}
        self.baseline_semantics = {"cooperate": "strategy1", "defect": "strategy2"}
        self.rng = random.Random(0)


class _StubAgent:
    def __init__(self, name: str) -> None:
        self.name = name
        self.strategies: list[str] = []


def _two_agent_game() -> tuple[_StubGame, _StubAgent, _StubAgent]:
    game = _StubGame()
    a, b = _StubAgent("a"), _StubAgent("b")
    game.agents = {"a": a, "b": b}
    return game, a, b


class TestSimpleBaselines(unittest.TestCase):
    def test_always_cooperate(self) -> None:
        game, a, _ = _two_agent_game()
        self.assertEqual(AlwaysCooperate().choose(a, game, 1), "strategy1")

    def test_always_defect(self) -> None:
        game, a, _ = _two_agent_game()
        self.assertEqual(AlwaysDefect().choose(a, game, 1), "strategy2")

    def test_random_choice_uses_game_rng(self) -> None:
        game, a, _ = _two_agent_game()
        result = RandomChoice().choose(a, game, 1)
        self.assertIn(result, {"strategy1", "strategy2"})


class TestTitForTat(unittest.TestCase):
    def test_starts_with_cooperate(self) -> None:
        game, a, _ = _two_agent_game()
        self.assertEqual(TitForTat().choose(a, game, 1), "strategy1")

    def test_mirrors_opponent_cooperation(self) -> None:
        game, a, b = _two_agent_game()
        b.strategies.append("Cooperate")
        self.assertEqual(TitForTat().choose(a, game, 2), "strategy1")

    def test_mirrors_opponent_defection(self) -> None:
        game, a, b = _two_agent_game()
        b.strategies.append("Defect")
        self.assertEqual(TitForTat().choose(a, game, 2), "strategy2")


class TestGrimTrigger(unittest.TestCase):
    def test_cooperate_when_opponent_never_defected(self) -> None:
        game, a, b = _two_agent_game()
        b.strategies.extend(["Cooperate", "Cooperate"])
        self.assertEqual(GrimTrigger().choose(a, game, 3), "strategy1")

    def test_defect_forever_after_first_defection(self) -> None:
        game, a, b = _two_agent_game()
        b.strategies.extend(["Cooperate", "Defect", "Cooperate"])
        # Once defection appears anywhere in history, grim defects.
        self.assertEqual(GrimTrigger().choose(a, game, 4), "strategy2")


class TestRandomMixed(unittest.TestCase):
    def test_invalid_distribution_rejected(self) -> None:
        with self.assertRaises(ValueError):
            RandomMixed({})
        with self.assertRaises(ValueError):
            RandomMixed({"strategy1": -0.5})
        with self.assertRaises(ValueError):
            RandomMixed({"strategy1": 0.0})

    def test_distribution_renormalised(self) -> None:
        rng = random.Random(0)
        s = RandomMixed({"strategy1": 4.0, "strategy2": 4.0}, rng=rng)
        self.assertAlmostEqual(sum(s.distribution.values()), 1.0)


class TestRegistry(unittest.TestCase):
    def test_baseline_id_parsing(self) -> None:
        self.assertTrue(is_baseline_id(f"{BASELINE_PREFIX}TitForTat"))
        self.assertFalse(is_baseline_id("OpenAIGPT4o"))

        name, kwargs = parse_baseline_id(f"{BASELINE_PREFIX}TitForTat")
        self.assertEqual((name, kwargs), ("TitForTat", {}))

        name, kwargs = parse_baseline_id(
            f"{BASELINE_PREFIX}RandomMixed(strategy1=0.7,strategy2=0.3)"
        )
        self.assertEqual(name, "RandomMixed")
        self.assertAlmostEqual(kwargs["strategy1"], 0.7)
        self.assertAlmostEqual(kwargs["strategy2"], 0.3)

    def test_make_baseline_unknown_strategy(self) -> None:
        with self.assertRaises(ValueError):
            make_baseline(f"{BASELINE_PREFIX}NotAStrategy")


if __name__ == "__main__":
    unittest.main()
