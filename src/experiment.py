"""Run multi-config experiments from a single manifest file.

A manifest is a JSON document of the form::

    {
      "experiment_name": "tom_ablation",
      "output_dir": "results/tom_ablation",
      "configs": [
        "resources/config/prisoner_dilemma_tom/pd_tom0.json",
        "resources/config/prisoner_dilemma_tom/pd_tom1.json",
        "resources/config/prisoner_dilemma_tom/pd_tom2.json"
      ],
      "seeds": [0, 1, 2, 3, 4],
      "aggregate_seeds": true,
      "config_overrides": { "nRounds": 10 }
    }

Each entry in ``configs`` is a path (relative to the manifest's location or
absolute). For each config, the runner:

1. Loads the JSON.
2. Applies ``config_overrides`` (a shallow merge).
3. Injects the manifest-level ``seeds`` if the config doesn't set its own.
4. Runs the FAIRGAME pipeline.
5. Writes per-config CSVs and (optionally) a seed-aggregated summary into
   ``output_dir``.

Invoke with::

    python -m src.experiment path/to/manifest.json
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.fairgame_factory import FairGameFactory
from src.io_managers.io_manager import IoManager
from src.results_processing.results_processor import ResultsProcessor
from src.results_processing.seed_aggregator import aggregate_seeds
from src.utils.logger import configure_logging, get_logger
from src.utils.utils import slug

configure_logging()
logger = get_logger(__name__)


class ExperimentError(RuntimeError):
    pass


@dataclass
class Manifest:
    name: str
    output_dir: Path
    configs: list[Path]
    seeds: list[int] | None = None
    aggregate_seeds: bool = True
    config_overrides: dict[str, Any] | None = None

    @classmethod
    def load(cls, path: Path) -> Manifest:
        path = path.resolve()
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)

        try:
            name = data["experiment_name"]
            output_dir = Path(data["output_dir"])
            configs = [Path(c) for c in data["configs"]]
        except KeyError as missing:
            raise ExperimentError(f"Manifest is missing required key {missing}") from missing

        # Resolve relative paths against the manifest directory.
        if not output_dir.is_absolute():
            output_dir = path.parent / output_dir
        configs = [c if c.is_absolute() else path.parent / c for c in configs]

        return cls(
            name=name,
            output_dir=output_dir,
            configs=configs,
            seeds=data.get("seeds"),
            aggregate_seeds=bool(data.get("aggregate_seeds", True)),
            config_overrides=data.get("config_overrides"),
        )


def run_manifest(manifest: Manifest) -> dict[str, Path]:
    """Execute every config in ``manifest`` and write CSV outputs.

    Returns a mapping ``{config_stem: csv_path}``.
    """
    manifest.output_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    processor = ResultsProcessor()

    for config_path in manifest.configs:
        if not config_path.is_file():
            raise ExperimentError(f"Config not found: {config_path}")
        with config_path.open("r", encoding="utf-8") as fh:
            config = json.load(fh)
        if manifest.config_overrides:
            config = {**config, **manifest.config_overrides}
        # Only inject manifest seeds when the config doesn't specify the key
        # at all. ``not config.get("seeds")`` also fired for an explicit
        # ``"seeds": []`` (a deliberate "no seeds" choice), silently
        # overriding it.
        if manifest.seeds is not None and "seeds" not in config:
            config["seeds"] = list(manifest.seeds)

        logger.info("Running %s", config_path.name)
        factory = FairGameFactory()
        # Use a default IoManager rooted at the project's resources/ directory
        # so 'templateFilename' continues to resolve normally.
        factory.set_io_manager(IoManager())
        outcomes = factory.create_and_run_games(config)
        df = processor.process(outcomes)

        stem = slug(config_path.stem) or config_path.stem
        per_seed_path = manifest.output_dir / f"{stem}_per_seed.csv"
        df.to_csv(per_seed_path, index=False)
        written[stem] = per_seed_path
        logger.info("Wrote %s (%d rows)", per_seed_path, len(df))

        if manifest.aggregate_seeds and "seed" in df.columns:
            agg = aggregate_seeds(df)
            agg_path = manifest.output_dir / f"{stem}_aggregated.csv"
            agg.to_csv(agg_path, index=False)
            written[f"{stem}_aggregated"] = agg_path
            logger.info("Wrote %s (%d rows)", agg_path, len(agg))

    summary_path = manifest.output_dir / "manifest_summary.json"
    with summary_path.open("w", encoding="utf-8") as fh:
        json.dump(
            {
                "experiment_name": manifest.name,
                "outputs": {k: str(v) for k, v in written.items()},
            },
            fh,
            indent=2,
        )
    return written


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python -m src.experiment <manifest.json>", file=sys.stderr)
        return 2
    manifest = Manifest.load(Path(sys.argv[1]))
    run_manifest(manifest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
