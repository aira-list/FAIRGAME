"""Tests for :mod:`src.factory.experiment`."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from src.factory.experiment import Manifest, run_manifest


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

    def test_manifest_missing_required_key_raises_experiment_error(self) -> None:
        from src.factory.experiment import ExperimentError

        bad = self.tmp / "bad.json"
        with bad.open("w", encoding="utf-8") as fh:
            json.dump({"experiment_name": "x"}, fh)
        with self.assertRaises(ExperimentError):
            Manifest.load(bad)

    def test_manifest_invalid_json_raises(self) -> None:
        bad = self.tmp / "bad.json"
        bad.write_text("definitely not json")
        with self.assertRaises(ValueError):  # json.JSONDecodeError is a ValueError subclass
            Manifest.load(bad)

    def test_manifest_missing_file_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            Manifest.load(self.tmp / "nonexistent.json")

    def test_relative_output_dir_resolved_against_manifest_location(self) -> None:
        manifest = Manifest.load(self.manifest_path)
        self.assertTrue(str(manifest.output_dir).startswith(str(self.tmp)))

    def test_default_aggregate_seeds_is_true(self) -> None:
        # Manifests that omit aggregate_seeds default to True.
        path = self.tmp / "no_agg.json"
        with path.open("w", encoding="utf-8") as fh:
            json.dump(
                {
                    "experiment_name": "noagg",
                    "output_dir": "out",
                    "configs": ["config.json"],
                },
                fh,
            )
        manifest = Manifest.load(path)
        self.assertTrue(manifest.aggregate_seeds)

    def test_run_manifest_writes_per_seed_and_aggregated_csv(self) -> None:
        manifest = Manifest.load(self.manifest_path)
        written = run_manifest(manifest)
        self.assertTrue(any(p.suffix == ".csv" and p.is_file() for p in written.values()))
        self.assertTrue(any(p.name.endswith("_per_seed.csv") for p in written.values()))
        self.assertTrue(any(p.name.endswith("_aggregated.csv") for p in written.values()))
        summary = manifest.output_dir / "manifest_summary.json"
        self.assertTrue(summary.is_file())
        summary_data = json.loads(summary.read_text(encoding="utf-8"))
        self.assertEqual(summary_data["experiment_name"], "test_exp")
        self.assertIn("outputs", summary_data)

    def test_run_manifest_skips_aggregation_when_disabled(self) -> None:
        # Patch the manifest to disable aggregation.
        path = self.tmp / "no_agg.json"
        with path.open("w", encoding="utf-8") as fh:
            json.dump(
                {
                    "experiment_name": "noagg",
                    "output_dir": "out_noagg",
                    "configs": ["config.json"],
                    "seeds": [1, 2],
                    "aggregate_seeds": False,
                },
                fh,
            )
        manifest = Manifest.load(path)
        written = run_manifest(manifest)
        # Per-seed CSV present; aggregated CSV absent.
        self.assertTrue(any(p.name.endswith("_per_seed.csv") for p in written.values()))
        self.assertFalse(any(p.name.endswith("_aggregated.csv") for p in written.values()))

    def test_run_manifest_applies_config_overrides(self) -> None:
        # nRounds=1 in the config; override to 3 via the manifest.
        path = self.tmp / "override.json"
        with path.open("w", encoding="utf-8") as fh:
            json.dump(
                {
                    "experiment_name": "overrideTest",
                    "output_dir": "out_override",
                    "configs": ["config.json"],
                    "seeds": [1],
                    "config_overrides": {"nRounds": 3},
                },
                fh,
            )
        manifest = Manifest.load(path)
        written = run_manifest(manifest)
        # Read the per-seed CSV and check max_rounds reflects the override.
        per_seed = next(p for p in written.values() if p.name.endswith("_per_seed.csv"))
        import pandas as pd

        df = pd.read_csv(per_seed)
        self.assertTrue((df["max_rounds"] == 3).all())

    def test_missing_config_file_raises_experiment_error(self) -> None:
        from src.factory.experiment import ExperimentError

        path = self.tmp / "missing.json"
        with path.open("w", encoding="utf-8") as fh:
            json.dump(
                {
                    "experiment_name": "x",
                    "output_dir": "out_x",
                    "configs": ["does_not_exist.json"],
                },
                fh,
            )
        manifest = Manifest.load(path)
        with self.assertRaises(ExperimentError):
            run_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
