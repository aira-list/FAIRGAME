"""Tests for :mod:`src.agents.baseline_strategies`."""

from __future__ import annotations

import random
import unittest
from collections import Counter

from src.agents.baseline_strategies import (
    BASELINE_PREFIX,
    AlwaysCooperate,
    AlwaysDefect,
    GrimTrigger,
    RandomChoice,
    RandomMixed,
    TitForTat,
    cooperate_key,
    defect_key,
    is_baseline_id,
    make_baseline,
    parse_baseline_id,
)

# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


class _StubAgent:
    def __init__(self, name: str) -> None:
        self.name = name
        self.strategies: list[str] = []


class _StubGame:
    def __init__(self, semantics: dict | None = None, seed: int = 0) -> None:
        self.payoff_matrix = type(
            "PM", (), {"strategies": {"strategy1": "Cooperate", "strategy2": "Defect"}}
        )()
        self.agents: dict[str, _StubAgent] = {}
        if semantics is not None:
            self.baseline_semantics = semantics
        self.rng = random.Random(seed)


def _two_agent_game(semantics=None, seed=0):
    game = _StubGame(
        semantics=semantics or {"cooperate": "strategy1", "defect": "strategy2"},
        seed=seed,
    )
    a, b = _StubAgent("a"), _StubAgent("b")
    game.agents = {"a": a, "b": b}
    return game, a, b


# ---------------------------------------------------------------------------
# cooperate_key / defect_key helpers
# ---------------------------------------------------------------------------


class TestSemanticsResolution(unittest.TestCase):
    def test_uses_explicit_semantics_when_provided(self) -> None:
        game = _StubGame(semantics={"cooperate": "strategy1", "defect": "strategy2"})
        self.assertEqual(cooperate_key(game), "strategy1")
        self.assertEqual(defect_key(game), "strategy2")

    def test_falls_back_to_first_and_last_strategy_keys(self) -> None:
        # No baseline_semantics attribute on the game — function must
        # default to (first_key, last_key).
        game = _StubGame(semantics=None)
        self.assertEqual(cooperate_key(game), "strategy1")
        self.assertEqual(defect_key(game), "strategy2")

    def test_explicit_override_can_swap_meanings(self) -> None:
        game = _StubGame(semantics={"cooperate": "strategy2", "defect": "strategy1"})
        self.assertEqual(cooperate_key(game), "strategy2")
        self.assertEqual(defect_key(game), "strategy1")


# ---------------------------------------------------------------------------
# Always-strategies
# ---------------------------------------------------------------------------


class TestAlwaysCooperate(unittest.TestCase):
    def test_returns_cooperate_key(self) -> None:
        game, a, _ = _two_agent_game()
        self.assertEqual(AlwaysCooperate().choose(a, game, 1), "strategy1")

    def test_consistent_across_rounds(self) -> None:
        game, a, _ = _two_agent_game()
        s = AlwaysCooperate()
        for r in range(1, 11):
            self.assertEqual(s.choose(a, game, r), "strategy1")

    def test_independent_of_opponent_history(self) -> None:
        game, a, b = _two_agent_game()
        b.strategies.extend(["Defect", "Defect", "Defect"])
        self.assertEqual(AlwaysCooperate().choose(a, game, 4), "strategy1")

    def test_name_is_always_cooperate(self) -> None:
        self.assertEqual(AlwaysCooperate().name, "always_cooperate")


class TestAlwaysDefect(unittest.TestCase):
    def test_returns_defect_key(self) -> None:
        game, a, _ = _two_agent_game()
        self.assertEqual(AlwaysDefect().choose(a, game, 1), "strategy2")

    def test_independent_of_opponent_history(self) -> None:
        game, a, b = _two_agent_game()
        b.strategies.extend(["Cooperate", "Cooperate"])
        self.assertEqual(AlwaysDefect().choose(a, game, 3), "strategy2")


# ---------------------------------------------------------------------------
# RandomChoice
# ---------------------------------------------------------------------------


class TestRandomChoice(unittest.TestCase):
    def test_only_returns_strategy_keys(self) -> None:
        game, a, _ = _two_agent_game()
        for r in range(1, 50):
            choice = RandomChoice().choose(a, game, r)
            self.assertIn(choice, {"strategy1", "strategy2"})

    def test_uses_game_rng_so_seeded_runs_match(self) -> None:
        game1, a, _ = _two_agent_game(seed=7)
        game2, a2, _ = _two_agent_game(seed=7)
        s1 = [RandomChoice().choose(a, game1, r) for r in range(20)]
        s2 = [RandomChoice().choose(a2, game2, r) for r in range(20)]
        self.assertEqual(s1, s2)

    def test_different_seeds_give_different_sequences(self) -> None:
        game1, a, _ = _two_agent_game(seed=1)
        game2, a2, _ = _two_agent_game(seed=2)
        s1 = [RandomChoice().choose(a, game1, r) for r in range(20)]
        s2 = [RandomChoice().choose(a2, game2, r) for r in range(20)]
        self.assertNotEqual(s1, s2)

    def test_explicit_rng_overrides_game_rng(self) -> None:
        game, a, _ = _two_agent_game(seed=7)
        # Two distinct RandomChoice instances with different RNGs should
        # produce distinct sequences when game.rng is unchanged.
        s = RandomChoice(rng=random.Random(99))
        s2 = RandomChoice(rng=random.Random(100))
        seq1 = [s.choose(a, game, r) for r in range(20)]
        seq2 = [s2.choose(a, game, r) for r in range(20)]
        self.assertNotEqual(seq1, seq2)


# ---------------------------------------------------------------------------
# TitForTat
# ---------------------------------------------------------------------------


class TestTitForTat(unittest.TestCase):
    def test_first_move_cooperates(self) -> None:
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

    def test_uses_only_most_recent_action(self) -> None:
        # History C, C, D — last move was D → defect.
        game, a, b = _two_agent_game()
        b.strategies.extend(["Cooperate", "Cooperate", "Defect"])
        self.assertEqual(TitForTat().choose(a, game, 4), "strategy2")
        # History D, D, C — last was C → cooperate.
        b.strategies.append("Cooperate")
        self.assertEqual(TitForTat().choose(a, game, 5), "strategy1")

    def test_with_multiple_opponents_defects_if_any_defected(self) -> None:
        game = _StubGame(semantics={"cooperate": "strategy1", "defect": "strategy2"})
        a, b, c = _StubAgent("a"), _StubAgent("b"), _StubAgent("c")
        b.strategies.append("Cooperate")
        c.strategies.append("Defect")
        game.agents = {"a": a, "b": b, "c": c}
        self.assertEqual(TitForTat().choose(a, game, 2), "strategy2")

    def test_with_multiple_opponents_cooperates_when_all_did(self) -> None:
        game = _StubGame(semantics={"cooperate": "strategy1", "defect": "strategy2"})
        a, b, c = _StubAgent("a"), _StubAgent("b"), _StubAgent("c")
        b.strategies.append("Cooperate")
        c.strategies.append("Cooperate")
        game.agents = {"a": a, "b": b, "c": c}
        self.assertEqual(TitForTat().choose(a, game, 2), "strategy1")


# ---------------------------------------------------------------------------
# GrimTrigger
# ---------------------------------------------------------------------------


class TestGrimTrigger(unittest.TestCase):
    def test_first_move_cooperates(self) -> None:
        game, a, _ = _two_agent_game()
        self.assertEqual(GrimTrigger().choose(a, game, 1), "strategy1")

    def test_cooperates_while_opponent_never_defected(self) -> None:
        game, a, b = _two_agent_game()
        b.strategies.extend(["Cooperate"] * 5)
        for r in range(2, 7):
            self.assertEqual(GrimTrigger().choose(a, game, r), "strategy1")

    def test_defects_forever_after_any_defection(self) -> None:
        game, a, b = _two_agent_game()
        b.strategies.extend(["Cooperate", "Defect", "Cooperate", "Cooperate"])
        # Even though opponent has been cooperating since, grim never forgives.
        self.assertEqual(GrimTrigger().choose(a, game, 5), "strategy2")

    def test_triggers_on_defection_anywhere_in_history(self) -> None:
        game, a, b = _two_agent_game()
        # Defect appears as the very first move, then cooperate forever.
        b.strategies.extend(["Defect"] + ["Cooperate"] * 9)
        self.assertEqual(GrimTrigger().choose(a, game, 11), "strategy2")

    def test_with_multiple_opponents_triggers_on_any(self) -> None:
        game = _StubGame(semantics={"cooperate": "strategy1", "defect": "strategy2"})
        a, b, c = _StubAgent("a"), _StubAgent("b"), _StubAgent("c")
        b.strategies.extend(["Cooperate", "Cooperate"])
        c.strategies.extend(["Cooperate", "Defect"])
        game.agents = {"a": a, "b": b, "c": c}
        self.assertEqual(GrimTrigger().choose(a, game, 3), "strategy2")


# ---------------------------------------------------------------------------
# RandomMixed
# ---------------------------------------------------------------------------


class TestRandomMixed(unittest.TestCase):
    def test_empty_distribution_rejected(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            RandomMixed({})
        self.assertIn("non-empty", str(ctx.exception).lower())

    def test_negative_probability_rejected(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            RandomMixed({"strategy1": -0.5})
        self.assertIn("negative", str(ctx.exception).lower())

    def test_zero_total_rejected(self) -> None:
        with self.assertRaises(ValueError):
            RandomMixed({"strategy1": 0.0})

    def test_distribution_is_renormalised_to_sum_one(self) -> None:
        s = RandomMixed({"strategy1": 4.0, "strategy2": 4.0})
        self.assertAlmostEqual(sum(s.distribution.values()), 1.0, places=6)

    def test_renormalisation_preserves_relative_proportions(self) -> None:
        s = RandomMixed({"strategy1": 8.0, "strategy2": 2.0})
        self.assertAlmostEqual(s.distribution["strategy1"] / s.distribution["strategy2"], 4.0)

    def test_sampling_respects_distribution_in_aggregate(self) -> None:
        # 95/5 mixed strategy → strategy1 should dominate by a wide margin.
        rng = random.Random(42)
        s = RandomMixed({"strategy1": 0.95, "strategy2": 0.05}, rng=rng)
        game, a, _ = _two_agent_game(seed=0)
        counts = Counter(s.choose(a, game, r) for r in range(2000))
        # With n=2000 the empirical share should be > 0.85 for strategy1.
        self.assertGreater(counts["strategy1"] / 2000, 0.85)

    def test_seeded_sampling_is_deterministic(self) -> None:
        s1 = RandomMixed({"strategy1": 0.5, "strategy2": 0.5}, rng=random.Random(7))
        s2 = RandomMixed({"strategy1": 0.5, "strategy2": 0.5}, rng=random.Random(7))
        game, a, _ = _two_agent_game()
        seq1 = [s1.choose(a, game, r) for r in range(50)]
        seq2 = [s2.choose(a, game, r) for r in range(50)]
        self.assertEqual(seq1, seq2)


# ---------------------------------------------------------------------------
# Registry / parsing
# ---------------------------------------------------------------------------


class TestRegistry(unittest.TestCase):
    def test_is_baseline_id_recognises_prefix(self) -> None:
        self.assertTrue(is_baseline_id(f"{BASELINE_PREFIX}TitForTat"))

    def test_is_baseline_id_accepts_lowercase_gui_prefix(self) -> None:
        # The web GUI emits the lowercase ``baseline:`` form; the factory must
        # still resolve it to a baseline rather than treat it as an LLM id.
        self.assertTrue(is_baseline_id("baseline:TitForTat"))
        self.assertEqual(make_baseline("baseline:AlwaysCooperate").name, "always_cooperate")
        name, kwargs = parse_baseline_id("baseline:RandomMixed(strategy1=0.7)")
        self.assertEqual(name, "RandomMixed")
        self.assertEqual(kwargs, {"strategy1": 0.7})

    def test_is_baseline_id_rejects_plain_model_names(self) -> None:
        self.assertFalse(is_baseline_id("OpenAIGPT4o"))

    def test_is_baseline_id_rejects_empty_and_non_strings(self) -> None:
        self.assertFalse(is_baseline_id(""))
        self.assertFalse(is_baseline_id(None))  # type: ignore[arg-type]
        self.assertFalse(is_baseline_id(42))  # type: ignore[arg-type]

    def test_parse_bare_form(self) -> None:
        self.assertEqual(
            parse_baseline_id(f"{BASELINE_PREFIX}TitForTat"),
            ("TitForTat", {}),
        )

    def test_parse_parametric_form(self) -> None:
        name, kwargs = parse_baseline_id(
            f"{BASELINE_PREFIX}RandomMixed(strategy1=0.7,strategy2=0.3)"
        )
        self.assertEqual(name, "RandomMixed")
        self.assertAlmostEqual(kwargs["strategy1"], 0.7)
        self.assertAlmostEqual(kwargs["strategy2"], 0.3)

    def test_parse_int_arguments(self) -> None:
        # Integer args (no decimal point) should be parsed as ints.
        name, kwargs = parse_baseline_id(f"{BASELINE_PREFIX}Foo(n=5)")
        self.assertEqual(name, "Foo")
        self.assertEqual(kwargs, {"n": 5})

    def test_parse_string_arguments_fall_through_unchanged(self) -> None:
        # Non-numeric values stay as strings.
        name, kwargs = parse_baseline_id(f"{BASELINE_PREFIX}Foo(label=abc)")
        self.assertEqual(kwargs, {"label": "abc"})

    def test_parse_invalid_argument_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_baseline_id(f"{BASELINE_PREFIX}Foo(broken)")

    def test_make_baseline_unknown_strategy_raises_with_known_list(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            make_baseline(f"{BASELINE_PREFIX}NotAStrategy")
        self.assertIn("NotAStrategy", str(ctx.exception))

    def test_make_baseline_returns_correct_class(self) -> None:
        s = make_baseline(f"{BASELINE_PREFIX}TitForTat")
        self.assertIsInstance(s, TitForTat)
        s = make_baseline(f"{BASELINE_PREFIX}AlwaysCooperate")
        self.assertIsInstance(s, AlwaysCooperate)
        s = make_baseline(f"{BASELINE_PREFIX}RandomMixed(strategy1=0.5,strategy2=0.5)")
        self.assertIsInstance(s, RandomMixed)


if __name__ == "__main__":
    unittest.main()
