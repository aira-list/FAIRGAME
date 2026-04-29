"""Smoke tests for the games imported from the Fairgame paper-evaluations repo.

Every new scenario must:
  * load and validate without errors,
  * run to completion under the fake LLM (registered by the test conftest),
  * yield a results DataFrame with the equilibrium / welfare columns wired in.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from src.fairgame_factory import FairGameFactory
from src.io_managers.io_manager import IoManager
from src.results_processing.results_processor import ResultsProcessor


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "resources" / "config"


def _load(rel_path: str) -> dict:
    return json.loads((CONFIG_DIR / rel_path).read_text(encoding="utf-8"))


def _factory() -> FairGameFactory:
    factory = FairGameFactory()
    factory.set_io_manager(IoManager())
    return factory


class TestPaperGamesLoadAndRun(unittest.TestCase):
    """Each shipped paper game runs end-to-end and emits non-empty results."""

    SCENARIOS = [
        ("Stag Hunt", "stag_hunt/stag_hunt_round_known.json"),
        ("Snowdrift", "snow_drift/snow_drift_round_known.json"),
        ("Harmony Game", "harmony_game/harmony_game_round_known.json"),
        ("Battle of the Sexes", "battle_sexes/battle_sexes_round_known.json"),
        ("Zero Sum", "zero_sum/zero_sum_round_known.json"),
    ]

    def test_each_scenario_runs(self) -> None:
        for label, rel_path in self.SCENARIOS:
            with self.subTest(scenario=label):
                config = _load(rel_path)
                factory = _factory()
                outcomes = factory.create_and_run_games(config)
                self.assertGreater(
                    len(outcomes), 0,
                    msg=f"{label} produced no games",
                )
                df = ResultsProcessor().process(outcomes)
                self.assertEqual(df.shape[0], len(outcomes))
                self.assertIn("welfare_mean_sum", df.columns)

    def test_equilibrium_metric_emitted_when_declared(self) -> None:
        # Stag Hunt declares two pure equilibria; expect the column.
        outcomes = _factory().create_and_run_games(
            _load("stag_hunt/stag_hunt_round_known.json")
        )
        df = ResultsProcessor().process(outcomes)
        self.assertIn("equilibrium_rate", df.columns)


class TestZeroSumPayoffStructure(unittest.TestCase):
    """Zero Sum uses a 2-weight matrix; ensure the per-round payoffs sum to 0."""

    def test_per_round_payoffs_cancel(self) -> None:
        outcomes = _factory().create_and_run_games(
            _load("zero_sum/zero_sum_round_known.json")
        )
        for game in outcomes.values():
            for entries in game["history"].values():
                total = sum(float(e["score"]) for e in entries if e.get("score") is not None)
                self.assertAlmostEqual(total, 0.0, places=5)


if __name__ == "__main__":
    unittest.main()
