"""Tests for :mod:`src.equilibrium`.

Covers known-good cases (the shipped 2x2 games), degenerate inputs that
should return an empty list, and the validator's auto-resolution path.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

from src.equilibrium import _two_player_payoff_arrays, compute_nash_equilibria
from src.io_managers.io_manager import IoManager


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load(rel: str) -> dict:
    return json.loads((PROJECT_ROOT / "resources" / "config" / rel).read_text())


# ---------------------------------------------------------------------------
# Known-good cases on the shipped scenarios
# ---------------------------------------------------------------------------

class TestKnownPureEquilibria(unittest.TestCase):
    def test_prisoner_dilemma_unique_pure_eq(self) -> None:
        cfg = _load("prisoner_dilemma/prisoner_dilemma_round_known_conventional.json")
        self.assertEqual(compute_nash_equilibria(cfg["payoffMatrix"]), ["combination4"])

    def test_stag_hunt_two_pure_eqs(self) -> None:
        cfg = _load("stag_hunt/stag_hunt_round_known.json")
        self.assertCountEqual(
            compute_nash_equilibria(cfg["payoffMatrix"]),
            ["combination1", "combination4"],
        )

    def test_battle_of_sexes_two_asymmetric_eqs(self) -> None:
        cfg = _load("battle_sexes/battle_sexes_round_known.json")
        self.assertCountEqual(
            compute_nash_equilibria(cfg["payoffMatrix"]),
            ["combination1", "combination4"],
        )

    def test_harmony_game_cooperation_dominates(self) -> None:
        cfg = _load("harmony_game/harmony_game_round_known.json")
        self.assertEqual(compute_nash_equilibria(cfg["payoffMatrix"]), ["combination1"])


# ---------------------------------------------------------------------------
# Degenerate / unsupported shapes
# ---------------------------------------------------------------------------

class TestDegenerateInputs(unittest.TestCase):
    """The function must never crash on shapes it can't handle."""

    def test_three_strategy_matrix_returns_empty(self) -> None:
        # Three pure strategies per player → not a 2x2.
        matrix = {
            "weights": {"w": 1},
            "strategies": {"en": {"strategy1": "A", "strategy2": "B", "strategy3": "C"}},
            "combinations": {},
            "matrix": {},
        }
        self.assertEqual(compute_nash_equilibria(matrix), [])

    def test_missing_combinations_returns_empty(self) -> None:
        cfg = _load("prisoner_dilemma/prisoner_dilemma_round_known_conventional.json")
        matrix = dict(cfg["payoffMatrix"])
        matrix.pop("combinations")
        self.assertEqual(compute_nash_equilibria(matrix), [])

    def test_missing_weights_returns_empty(self) -> None:
        cfg = _load("prisoner_dilemma/prisoner_dilemma_round_known_conventional.json")
        matrix = dict(cfg["payoffMatrix"])
        matrix.pop("weights")
        self.assertEqual(compute_nash_equilibria(matrix), [])

    def test_unknown_language_returns_empty(self) -> None:
        cfg = _load("prisoner_dilemma/prisoner_dilemma_round_known_conventional.json")
        self.assertEqual(compute_nash_equilibria(cfg["payoffMatrix"], language="zz"), [])

    def test_non_canonical_combination_keys_return_empty(self) -> None:
        # Two strategies but combinations renamed away from combination1..4.
        matrix = {
            "weights": {"w1": 1, "w2": 2},
            "strategies": {"en": {"strategy1": "A", "strategy2": "B"}},
            "combinations": {
                "alpha": ["strategy1", "strategy1"],
                "beta": ["strategy1", "strategy2"],
                "gamma": ["strategy2", "strategy1"],
                "delta": ["strategy2", "strategy2"],
            },
            "matrix": {
                "alpha": ["w1", "w1"],
                "beta": ["w1", "w2"],
                "gamma": ["w2", "w1"],
                "delta": ["w2", "w2"],
            },
        }
        self.assertEqual(compute_nash_equilibria(matrix), [])


# ---------------------------------------------------------------------------
# Mixed-strategy-only cases (matching pennies)
# ---------------------------------------------------------------------------

class TestMixedStrategyOnly(unittest.TestCase):
    """Matching pennies has no pure Nash equilibrium — the result must be []."""

    def test_matching_pennies_no_pure_eq(self) -> None:
        matrix = {
            "weights": {"w_pos": 1, "w_neg": -1},
            "strategies": {"en": {"strategy1": "Heads", "strategy2": "Tails"}},
            "combinations": {
                "combination1": ["strategy1", "strategy1"],
                "combination2": ["strategy1", "strategy2"],
                "combination3": ["strategy2", "strategy1"],
                "combination4": ["strategy2", "strategy2"],
            },
            "matrix": {
                # Row wins on match, loses on mismatch.
                "combination1": ["w_pos", "w_neg"],
                "combination2": ["w_neg", "w_pos"],
                "combination3": ["w_neg", "w_pos"],
                "combination4": ["w_pos", "w_neg"],
            },
        }
        self.assertEqual(compute_nash_equilibria(matrix), [])


# ---------------------------------------------------------------------------
# Internal helper: array builder
# ---------------------------------------------------------------------------

class TestPayoffArrayBuilder(unittest.TestCase):
    def test_builds_2x2_arrays_for_pd(self) -> None:
        cfg = _load("prisoner_dilemma/prisoner_dilemma_round_known_conventional.json")
        arrays = _two_player_payoff_arrays(cfg["payoffMatrix"])
        self.assertIsNotNone(arrays)
        a, b = arrays
        self.assertEqual(a.shape, (2, 2))
        self.assertEqual(b.shape, (2, 2))
        # Symmetric game → A and B should be transposes of each other.
        import numpy as np

        self.assertTrue(np.array_equal(a, b.T))

    def test_returns_none_for_three_strategy(self) -> None:
        matrix = {
            "weights": {"w": 1},
            "strategies": {"en": {f"strategy{i}": str(i) for i in range(1, 4)}},
            "combinations": {},
            "matrix": {},
        }
        self.assertIsNone(_two_player_payoff_arrays(matrix))


# ---------------------------------------------------------------------------
# Validator integration: equilibria: "auto"
# ---------------------------------------------------------------------------

class TestAutoEquilibriaResolution(unittest.TestCase):
    def test_auto_replaced_with_resolved_list_for_pd(self) -> None:
        cfg = _load("prisoner_dilemma/prisoner_dilemma_round_known_conventional.json")
        cfg["equilibria"] = "auto"
        out = IoManager().process_and_validate_configuration(cfg)
        self.assertEqual(out["equilibria"], ["combination4"])

    def test_auto_replaced_for_stag_hunt(self) -> None:
        cfg = _load("stag_hunt/stag_hunt_round_known.json")
        cfg["equilibria"] = "auto"
        out = IoManager().process_and_validate_configuration(cfg)
        self.assertCountEqual(out["equilibria"], ["combination1", "combination4"])

    def test_explicit_list_left_alone(self) -> None:
        cfg = _load("prisoner_dilemma/prisoner_dilemma_round_known_conventional.json")
        cfg["equilibria"] = ["combination1"]  # nonsense but explicit
        out = IoManager().process_and_validate_configuration(cfg)
        self.assertEqual(out["equilibria"], ["combination1"])

    def test_empty_list_left_alone(self) -> None:
        cfg = _load("prisoner_dilemma/prisoner_dilemma_round_known_conventional.json")
        cfg["equilibria"] = []
        out = IoManager().process_and_validate_configuration(cfg)
        self.assertEqual(out["equilibria"], [])


# ---------------------------------------------------------------------------
# Missing optional dependency
# ---------------------------------------------------------------------------

class TestMissingNashpy(unittest.TestCase):
    """If nashpy isn't installed, callers should get a clear ImportError."""

    def test_clear_import_error_when_nashpy_unavailable(self) -> None:
        with mock.patch.dict(sys.modules, {"nashpy": None}):
            cfg = _load("prisoner_dilemma/prisoner_dilemma_round_known_conventional.json")
            with self.assertRaises(ImportError) as exc:
                compute_nash_equilibria(cfg["payoffMatrix"])
            self.assertIn("nashpy", str(exc.exception).lower())


if __name__ == "__main__":
    unittest.main()
