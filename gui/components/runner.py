"""Run a config from the GUI and persist results.

The runner is the single seam between the Streamlit UI and the FAIRGAME
engine. It is intentionally side-effecting:

* writes the resolved config to disk as ``config.json``;
* runs the pipeline once via :class:`FairGameFactory`;
* writes the per-game DataFrame as ``results.csv``;
* writes the raw history dict as ``raw_results.json`` (for the Results page).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from gui.components.state import RESULTS_DIR
from src.fairgame_factory import FairGameFactory
from src.io_managers.io_manager import IoManager
from src.results_processing.results_processor import ResultsProcessor
from src.results_processing.seed_aggregator import aggregate_seeds
from src.utils.logger import get_logger
from src.utils.utils import slug

logger = get_logger(__name__)


@dataclass
class RunOutcome:
    name: str
    timestamp: str
    output_dir: Path
    config: Dict[str, Any]
    raw: Dict[str, Any]
    df: pd.DataFrame
    aggregated: Optional[pd.DataFrame] = None

    def to_session_payload(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "timestamp": self.timestamp,
            "output_dir": str(self.output_dir),
        }


def run_config(config: Dict[str, Any], display_name: str = "") -> RunOutcome:
    """Run ``config`` end-to-end and persist artefacts under ``results/gui/``."""
    name = display_name or config.get("name", "fairgame-run")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = RESULTS_DIR / f"{timestamp}_{slug(name) or 'run'}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Persist exactly what the engine sees. We also save a copy of the
    # original (potentially user-edited) config so the run is replayable.
    (output_dir / "config.json").write_text(
        json.dumps(config, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    factory = FairGameFactory()
    factory.set_io_manager(IoManager())
    raw = factory.create_and_run_games(config)

    df = ResultsProcessor().process(raw)

    aggregated: Optional[pd.DataFrame] = None
    if "seed" in df.columns and df["seed"].nunique(dropna=True) > 1:
        aggregated = aggregate_seeds(df)
        aggregated.to_csv(output_dir / "results_aggregated.csv", index=False)

    df.to_csv(output_dir / "results.csv", index=False)
    (output_dir / "raw_results.json").write_text(
        json.dumps(raw, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    logger.info("Run %s written to %s", name, output_dir)

    return RunOutcome(
        name=name,
        timestamp=timestamp,
        output_dir=output_dir,
        config=config,
        raw=raw,
        df=df,
        aggregated=aggregated,
    )


def list_past_runs() -> list[Path]:
    """Return run directories under ``results/gui/`` newest first."""
    if not RESULTS_DIR.is_dir():
        return []
    runs = [p for p in RESULTS_DIR.iterdir() if p.is_dir()]
    runs.sort(key=lambda p: p.name, reverse=True)
    return runs


def load_past_run(run_dir: Path) -> RunOutcome:
    """Reload a persisted run from disk for the Results page."""
    config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    raw = json.loads((run_dir / "raw_results.json").read_text(encoding="utf-8"))
    df = pd.read_csv(run_dir / "results.csv")
    aggregated_path = run_dir / "results_aggregated.csv"
    aggregated = pd.read_csv(aggregated_path) if aggregated_path.is_file() else None
    # Pull name + timestamp from the directory name: ``YYYYMMDD_HHMMSS_<slug>``.
    parts = run_dir.name.split("_", 2)
    timestamp = "_".join(parts[:2]) if len(parts) >= 2 else run_dir.name
    name = parts[2] if len(parts) >= 3 else run_dir.name
    return RunOutcome(
        name=name,
        timestamp=timestamp,
        output_dir=run_dir,
        config=config,
        raw=raw,
        df=df,
        aggregated=aggregated,
    )
