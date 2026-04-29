"""Tests for :mod:`src.equilibrium`."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from src.equilibrium import compute_nash_equilibria
from src.io_managers.io_manager import IoManager


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load(rel: str) -> dict:
    return json.loads((PROJECT_ROOT / "resources" / "config" / rel).read_text())


class TestNashEquilibria(unittest.TestCase):
    def test_prisoner_dilemma_unique_pure_eq(self) -> None:
        cfg = _load("prisoner_dilemma/prisoner_dilemma_round_known_conventional.json")
        eqs = compute_nash_equilibria(cfg["payoffMatrix"])
        self.assertEqual(eqs, ["combination4"])

    def test_stag_hunt_two_pure_eqs(self) -> None:
        cfg = _load("stag_hunt/stag_hunt_round_known.json")
        eqs = compute_nash_equilibria(cfg["payoffMatrix"])
        self.assertCountEqual(eqs, ["combination1", "combination4"])

    def test_battle_of_sexes_two_asymmetric_eqs(self) -> None:
        cfg = _load("battle_sexes/battle_sexes_round_known.json")
        eqs = compute_nash_equilibria(cfg["payoffMatrix"])
        self.assertCountEqual(eqs, ["combination1", "combination4"])

    def test_harmony_cooperation_dominates(self) -> None:
        cfg = _load("harmony_game/harmony_game_round_known.json")
        eqs = compute_nash_equilibria(cfg["payoffMatrix"])
        self.assertEqual(eqs, ["combination1"])


class TestAutoEquilibriaResolution(unittest.TestCase):
    def test_validator_replaces_auto_with_resolved_list(self) -> None:
        cfg = _load("prisoner_dilemma/prisoner_dilemma_round_known_conventional.json")
        cfg["equilibria"] = "auto"
        out = IoManager().process_and_validate_configuration(cfg)
        self.assertEqual(out["equilibria"], ["combination4"])

    def test_validator_leaves_explicit_list_alone(self) -> None:
        cfg = _load("prisoner_dilemma/prisoner_dilemma_round_known_conventional.json")
        cfg["equilibria"] = ["combination1"]  # nonsense but explicit
        out = IoManager().process_and_validate_configuration(cfg)
        self.assertEqual(out["equilibria"], ["combination1"])


if __name__ == "__main__":
    unittest.main()
