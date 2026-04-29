"""Tests for :mod:`src.experiment`."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from src.experiment import Manifest, run_manifest


def _inline_config() -> dict:
    """A self-contained config that does not require any template lookup."""
    return {
        "name": "manifest test",
        "nRounds": 1,
        "nRoundsIsKnown": True,
        "llm": "OpenAIGPT4o",
        "languages": ["en"],
        "allAgentPermutations": False,
        "agents": {
            "names": ["a1", "a2"],
            "personalities": {"en": ["cooperative", "selfish"]},
            "opponentPersonalityProb": [0, 0],
        },
        "promptTemplate": {
            "en": "{currentPlayerName} chooses between {strategy1} and {strategy2}."
        },
        "payoffMatrix": {
            "weights": {"weight1": 6, "weight2": 10, "weight3": 0, "weight4": 2},
            "strategies": {"en": {"strategy1": "Cooperate", "strategy2": "Defect"}},
            "combinations": {
                "combination1": ["strategy1", "strategy1"],
                "combination4": ["strategy2", "strategy2"],
            },
            "matrix": {
                "combination1": ["weight1", "weight1"],
                "combination4": ["weight4", "weight4"],
            },
        },
        "stopGameWhen": [],
        "agentsCommunicate": False,
        "equilibria": ["combination4"],
    }


class TestManifest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="fairgame_exp_"))
        self.config_path = self.tmp / "config.json"
        with self.config_path.open("w", encoding="utf-8") as fh:
            json.dump(_inline_config(), fh)

        self.manifest_path = self.tmp / "manifest.json"
        with self.manifest_path.open("w", encoding="utf-8") as fh:
            json.dump(
                {
                    "experiment_name": "test_exp",
                    "output_dir": "out",
                    "configs": ["config.json"],
                    "seeds": [1, 2],
                    "aggregate_seeds": True,
                },
                fh,
            )

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_manifest_load_resolves_paths(self) -> None:
        manifest = Manifest.load(self.manifest_path)
        self.assertEqual(manifest.name, "test_exp")
        self.assertTrue(manifest.output_dir.is_absolute())
        self.assertTrue(manifest.configs[0].is_absolute())
        self.assertEqual(manifest.seeds, [1, 2])

    def test_manifest_missing_required_key(self) -> None:
        bad = self.tmp / "bad.json"
        with bad.open("w", encoding="utf-8") as fh:
            json.dump({"experiment_name": "x"}, fh)
        with self.assertRaises(Exception):
            Manifest.load(bad)

    def test_run_manifest_writes_per_seed_and_aggregated_csv(self) -> None:
        manifest = Manifest.load(self.manifest_path)
        written = run_manifest(manifest)
        self.assertTrue(any(p.suffix == ".csv" and p.is_file() for p in written.values()))
        # 2 seeds + aggregate=True ⇒ both per-seed and aggregated outputs.
        self.assertTrue(any(p.name.endswith("_per_seed.csv") for p in written.values()))
        self.assertTrue(any(p.name.endswith("_aggregated.csv") for p in written.values()))
        summary = manifest.output_dir / "manifest_summary.json"
        self.assertTrue(summary.is_file())
        summary_data = json.loads(summary.read_text(encoding="utf-8"))
        self.assertEqual(summary_data["experiment_name"], "test_exp")


if __name__ == "__main__":
    unittest.main()
