"""Run-history persistence: save / list / load + starter-run seeding.

Each run lives under ``RUNS_DIR/<run_id>/`` with:

* ``metadata.json`` — request config + timestamp + row count.
* ``rows.json``     — the canonical result rows, stored as native JSON so
  list-valued cells (per-round strategies/scores/beliefs) round-trip as real
  lists. This is what :func:`load_run` returns and what the dashboards /
  compare views consume — the same shape the ``/run`` endpoint returns live.
* ``results.csv``   — a derived, human-/Excel-friendly export for download.
  List cells become their string repr here; it is never read back for
  analysis (only served by the CSV endpoint).

Runs written before ``rows.json`` existed carry only ``results.csv``;
:func:`load_run` falls back to parsing it (list cells come back as repr
strings, which the dashboard/compare parsers still tolerate).

``RUNS_DIR`` is imported from :mod:`web_api.storage` — tests monkey-patch
``web_api.storage.RUNS_DIR`` to redirect into a tempdir.
"""

from __future__ import annotations

import json
import math
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import HTTPException

from src.utils.logger import get_logger
from web_api import storage

logger = get_logger(__name__)


def _runs_dir() -> Path:
    """Live read of ``RUNS_DIR`` so test-time monkey-patches take effect."""
    return storage.RUNS_DIR


# Shipped sample runs (real engine output, produced by
# ``tools/populate_seed_results.py``) — copied into RUNS_DIR at startup so a
# fresh install has results to visualise before running anything.
STARTER_RUNS_DIR = Path(__file__).resolve().parent.parent / "starter_library" / "runs"


def seed_starter_runs() -> None:
    """Copy shipped sample runs into ``RUNS_DIR`` (top-up by run id).

    Mirrors the library-store seed top-up: a run directory is copied only
    when its id is absent, so user-generated runs and previously copied
    starters are never touched. Called from the app's startup hook — never
    at import time. Set ``FAIRGAME_SKIP_STARTER_RUNS=1`` to opt out (e.g.
    after deliberately deleting the samples).

    Concurrent-safe for multi-worker servers: each run is copied to a
    process-unique temp directory and atomically renamed into place; the
    loser of a race simply discards its copy instead of crashing.
    """
    if os.getenv("FAIRGAME_SKIP_STARTER_RUNS", "").strip().lower() in {"1", "true", "yes", "on"}:
        return
    if not STARTER_RUNS_DIR.is_dir():
        return
    runs_dir = _runs_dir()
    runs_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for src in sorted(STARTER_RUNS_DIR.iterdir()):
        if not (src / "metadata.json").is_file():
            continue
        dst = runs_dir / src.name
        if dst.exists():
            continue
        tmp = runs_dir / f".{src.name}.seed-tmp-{os.getpid()}"
        try:
            shutil.copytree(src, tmp)
            tmp.rename(dst)  # atomic; fails if a sibling worker won the race
            copied += 1
        except OSError:
            shutil.rmtree(tmp, ignore_errors=True)
    if copied:
        logger.info("Seeded %d starter run(s) into %s", copied, runs_dir)


def save_run(
    run_id: str,
    config: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    configuration_id: str | None = None,
) -> Path:
    """Write a run's metadata + CSV payload to ``RUNS_DIR/<run_id>/``.

    ``configuration_id`` links the run back to the saved library
    configuration that produced it, so a configuration can be exported
    together with its related results.
    """
    run_dir = _runs_dir() / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_rows(run_dir, rows)
    metadata = {
        "id": run_id,
        "name": config.get("name", "(unnamed)"),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "configuration_id": configuration_id,
        "config": config,
        "n_rows": len(rows),
    }
    (run_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))
    return run_dir


def _write_rows(run_dir: Path, rows: list[dict[str, Any]]) -> None:
    """Persist ``rows`` as canonical JSON plus a derived CSV export.

    ``rows.json`` preserves native types (lists stay lists); ``results.csv``
    is only for the download endpoint. Rows are already JSON-native (they
    are what the ``/run`` endpoint returns), so no coercion is needed.
    """
    (run_dir / "rows.json").write_text(json.dumps(rows, indent=2))
    pd.DataFrame(rows).to_csv(run_dir / "results.csv", index=False)


def runs_for_configuration(config_id: str) -> list[dict[str, Any]]:
    """All runs whose ``configuration_id`` matches, newest first, each with
    its result rows attached (the shape :func:`load_run` returns)."""
    out: list[dict[str, Any]] = []
    for meta in list_runs():
        if meta.get("configuration_id") == config_id:
            out.append(load_run(meta["id"]))
    return out


def import_run(run_id: str, metadata: dict[str, Any], rows: list[dict[str, Any]]) -> Path:
    """Recreate a run from an exported bundle: write the supplied metadata
    (already re-stamped with a new id / configuration_id) verbatim plus its
    CSV rows. Unlike :func:`save_run` this preserves the original timestamp
    and name rather than minting fresh ones."""
    run_dir = _runs_dir() / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_rows(run_dir, rows)
    (run_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))
    return run_dir


def list_runs() -> list[dict[str, Any]]:
    """All persisted runs, newest first.

    Run ids are random hex, so directory order is meaningless — sort by the
    metadata timestamp instead.
    """
    runs: list[dict[str, Any]] = []
    runs_dir = _runs_dir()
    if not runs_dir.is_dir():
        return runs
    for child in runs_dir.iterdir():
        meta_file = child / "metadata.json"
        if not meta_file.is_file():
            continue
        try:
            runs.append(json.loads(meta_file.read_text()))
        except json.JSONDecodeError:
            logger.warning("Skipping malformed run metadata at %s", meta_file)
    runs.sort(key=lambda m: str(m.get("timestamp") or ""), reverse=True)
    return runs


def load_run(run_id: str) -> dict[str, Any]:
    if not storage.is_safe_segment(run_id):
        raise HTTPException(status_code=404, detail=f"Run {run_id!r} not found.")
    run_dir = _runs_dir() / run_id
    meta_file = run_dir / "metadata.json"
    if not meta_file.is_file():
        raise HTTPException(status_code=404, detail=f"Run {run_id!r} not found.")
    metadata = json.loads(meta_file.read_text())

    # Canonical path: native-typed rows preserved as JSON.
    rows_file = run_dir / "rows.json"
    if rows_file.is_file():
        return {**metadata, "rows": json.loads(rows_file.read_text())}

    # Legacy path: runs written before rows.json carry only results.csv.
    csv_file = run_dir / "results.csv"
    if not csv_file.is_file():
        raise HTTPException(status_code=404, detail=f"Run {run_id!r} not found.")
    try:
        df = pd.read_csv(csv_file)
    except pd.errors.EmptyDataError:
        # A run with zero result rows writes a column-less CSV; treat it as an
        # empty result set rather than surfacing a 500.
        return {**metadata, "rows": []}
    # CSV round-tripping yields NaN for blank cells; NaN is not valid JSON
    # (Starlette serialises with allow_nan=False), so coerce to None here.
    rows = [
        {k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in row.items()}
        for row in df.to_dict(orient="records")
    ]
    return {**metadata, "rows": rows}
