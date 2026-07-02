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

import pytest

from src.equilibrium import _two_player_payoff_arrays, compute_nash_equilibria
from src.io_managers.io_manager import IoManager
from src.utils.utils import get_resources_dir
from unit_tests.support import RESOURCES_SKIP_REASON, resources_available

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load(rel: str) -> dict:
    # These fixtures live in the sibling paper-evaluations resources folder,
    # which isn't shipped here; skip the (only the) tests that need them.
    if not resources_available():
        pytest.skip(RESOURCES_SKIP_REASON)
    return json.loads((get_resources_dir() / "config" / rel).read_text())


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


# ---------------------------------------------------------------------------
# mutmut-driven coverage
# ---------------------------------------------------------------------------


class TestPartialBlockMismatch(unittest.TestCase):
    def test_combinations_present_but_weight_matrix_missing_a_key(self) -> None:
        # All four canonical combination keys are declared in
        # ``combinations``, but ``matrix`` is missing one of them. The
        # function MUST detect this asymmetry and bail out (return []).
        # The completeness check has to use ``and`` (both blocks contain
        # the key), not ``or`` (either contains it) — otherwise the
        # function later KeyErrors looking up the missing entry.
        cfg = _load("prisoner_dilemma/prisoner_dilemma_round_known_conventional.json")
        matrix = json.loads(json.dumps(cfg["payoffMatrix"]))  # deep copy
        del matrix["matrix"]["combination4"]
        self.assertEqual(compute_nash_equilibria(matrix), [])

    def test_weight_matrix_present_but_combinations_missing_a_key(self) -> None:
        cfg = _load("prisoner_dilemma/prisoner_dilemma_round_known_conventional.json")
        matrix = json.loads(json.dumps(cfg["payoffMatrix"]))
        del matrix["combinations"]["combination4"]
        self.assertEqual(compute_nash_equilibria(matrix), [])


class TestMissingWeightKeyDefaults(unittest.TestCase):
    """A weight key referenced in ``matrix`` but absent from ``weights``
    must contribute 0.0 to the payoff arrays — never an arbitrary
    non-zero default that would distort the NE computation."""

    def _matrix_with_unique_eq_at(self, combo_idx: int) -> dict:
        """Build a 2x2 game whose unique pure NE is at the given (i,j).

        ``combo_idx`` is 0..3 mapping to combination1..4 in row-major
        order: 0=(0,0), 1=(0,1), 2=(1,0), 3=(1,1).
        """
        # Diagonal-dominance trick: row's dominant strategy = i, col's = j.
        i, j = divmod(combo_idx, 2)
        # Row prefers strategy `i` regardless of col.
        # Col prefers strategy `j` regardless of row.
        a = [[5 if r == i else 0 for c in range(2)] for r in range(2)]
        b = [[5 if c == j else 0 for c in range(2)] for r in range(2)]
        return {
            "weights": {"hi": 5, "lo": 0},
            "strategies": {"en": {"strategy1": "X", "strategy2": "Y"}},
            "combinations": {
                "combination1": ["strategy1", "strategy1"],
                "combination2": ["strategy1", "strategy2"],
                "combination3": ["strategy2", "strategy1"],
                "combination4": ["strategy2", "strategy2"],
            },
            "matrix": {
                "combination1": ["hi" if a[0][0] else "lo", "hi" if b[0][0] else "lo"],
                "combination2": ["hi" if a[0][1] else "lo", "hi" if b[0][1] else "lo"],
                "combination3": ["hi" if a[1][0] else "lo", "hi" if b[1][0] else "lo"],
                "combination4": ["hi" if a[1][1] else "lo", "hi" if b[1][1] else "lo"],
            },
        }

    def test_player_zero_weight_default_is_zero(self) -> None:
        # Game with NE at combination1 (both prefer s1). Now corrupt the
        # row-player slot at (0,0) by referencing a weight key that
        # doesn't exist in ``weights``. Default=0 keeps row indifferent
        # at col=s1 → both combination1 and combination3 become NE.
        # Default=1 (the surviving mutant) breaks the tie in s1's favour
        # → only combination1, missing combination3. We assert the
        # presence of combination3 to pin the default down.
        m = self._matrix_with_unique_eq_at(0)
        m["matrix"]["combination1"] = ["w_missing_for_row", "hi"]
        self.assertIn("combination3", compute_nash_equilibria(m))

    def test_player_one_weight_default_is_zero(self) -> None:
        # Symmetric variant: corrupt the col-player slot at (0,0).
        # Default=0 → combination2 becomes a tied NE. Default=1 → only
        # combination1 survives.
        m = self._matrix_with_unique_eq_at(0)
        m["matrix"]["combination1"] = ["hi", "w_missing_for_col"]
        self.assertIn("combination2", compute_nash_equilibria(m))


class TestComboForPureMappings(unittest.TestCase):
    """The combo_for_pure dict must map each (i, j) to the right combination.

    Every existing fixture has its NE at combination1 or combination4 —
    so mutating combination2's or combination3's entry survived. These
    tests pin those two diagonals down with games whose unique pure NE
    sits at combination2 / combination3.
    """

    def _dominance_game(self, row_dom: int, col_dom: int) -> dict:
        # Row pays 5 only when it plays `row_dom`; col pays 5 only when
        # it plays `col_dom`. Unique NE at (row_dom, col_dom).
        def w(player_dom: int, idx: int) -> str:
            return "hi" if idx == player_dom else "lo"

        return {
            "weights": {"hi": 5, "lo": 0},
            "strategies": {"en": {"strategy1": "X", "strategy2": "Y"}},
            "combinations": {
                "combination1": ["strategy1", "strategy1"],
                "combination2": ["strategy1", "strategy2"],
                "combination3": ["strategy2", "strategy1"],
                "combination4": ["strategy2", "strategy2"],
            },
            "matrix": {
                "combination1": [w(row_dom, 0), w(col_dom, 0)],
                "combination2": [w(row_dom, 0), w(col_dom, 1)],
                "combination3": [w(row_dom, 1), w(col_dom, 0)],
                "combination4": [w(row_dom, 1), w(col_dom, 1)],
            },
        }

    def test_unique_ne_at_combination2(self) -> None:
        # Row dominant on s1 (=index 0), col dominant on s2 (=index 1).
        # NE = (0, 1) → combination2.
        self.assertEqual(
            compute_nash_equilibria(self._dominance_game(row_dom=0, col_dom=1)),
            ["combination2"],
        )

    def test_unique_ne_at_combination3(self) -> None:
        # Row dominant on s2, col dominant on s1.
        # NE = (1, 0) → combination3.
        self.assertEqual(
            compute_nash_equilibria(self._dominance_game(row_dom=1, col_dom=0)),
            ["combination3"],
        )


if __name__ == "__main__":
    unittest.main()
