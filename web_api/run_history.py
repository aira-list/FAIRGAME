"""Run-history persistence: save / list / load + synthetic-demo seeding.

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

import hashlib
import json
import math
import random
from datetime import datetime, timedelta
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


def save_run(
    run_id: str,
    config: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    configuration_id: str | None = None,
    demo: bool = False,
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
        # Provenance: true when produced by the offline demo fake, so demo runs
        # are never mistaken for real LLM results in history / compare / export.
        "demo": demo,
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
    CSV rows. Unlike :func:`save_run` this preserves the original timestamp,
    name and demo flag rather than minting fresh ones."""
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


def seed_synthetic_runs() -> None:
    """Generate a handful of demo runs so the Results page has data on a
    fresh install.

    Disabled by default — FAIRGAME starts with no runs. The caller
    (``web_api.main``) gates on ``FAIRGAME_SEED_DEMO_RUNS``; the only guard
    here is idempotence: skipped when ``RUNS_DIR`` already contains anything.
    """
    runs_dir = _runs_dir()
    if any(runs_dir.iterdir()) if runs_dir.is_dir() else False:
        return

    scenarios = [
        (
            "syn_pd_001",
            "Prisoner's Dilemma — classic, demo",
            "Cooperate",
            "Defect",
            (3, 5, 0, 1),
            ["cooperative", "selfish"],
            [0.30, 0.55],
            8,
            5,
        ),
        (
            "syn_sh_001",
            "Stag Hunt — payoff vs risk",
            "Stag",
            "Hare",
            (4, 1, 0, 2),
            ["cooperative", "cooperative"],
            [0.65, 0.70],
            6,
            4,
        ),
        (
            "syn_bos_001",
            "Battle of the Sexes — coordination",
            "Concert",
            "Match",
            (2, 1, 0, 0),
            ["assertive", "agreeable"],
            [0.55, 0.40],
            5,
            3,
        ),
        (
            "syn_sd_001",
            "Snowdrift — anti-coordination",
            "Shovel",
            "Stay",
            (3, 1, 4, 0),
            ["dutiful", "selfish"],
            [0.62, 0.35],
            7,
            4,
        ),
        (
            "syn_h_001",
            "Harmony Game — dominant cooperation",
            "Help",
            "Slack",
            (5, 2, 4, 1),
            ["altruistic", "altruistic"],
            [0.92, 0.88],
            5,
            4,
        ),
    ]
    now = datetime.now()
    for offset, (sid, name, A, B, weights, styles, coop, n_games, n_rounds) in enumerate(scenarios):
        # Stable across processes: builtin ``hash()`` is salted per-process
        # (PYTHONHASHSEED), so "deterministic demo" runs would differ across
        # restarts. A hashlib digest gives the same seed every time.
        seed = int.from_bytes(hashlib.sha256(sid.encode()).digest()[:4], "big")
        rng = random.Random(seed)
        run_dir = runs_dir / sid
        run_dir.mkdir(parents=True, exist_ok=True)
        R, S, T, P = weights
        rows: list[dict[str, Any]] = []
        for g in range(n_games):
            strats = [
                [A if rng.random() < coop[a] else B for _ in range(n_rounds)] for a in range(2)
            ]
            s0: list[float] = []
            s1: list[float] = []
            for r in range(n_rounds):
                x, y = strats[0][r], strats[1][r]
                if x == A and y == A:
                    a, b = R, R
                elif x == A and y == B:
                    a, b = S, T
                elif x == B and y == A:
                    a, b = T, S
                else:
                    a, b = P, P
                s0.append(a)
                s1.append(b)
            wsum = sum(s0) + sum(s1)
            wmin = min(sum(s0), sum(s1))
            wgini = abs(sum(s0) - sum(s1)) / max(wsum, 1) / 2
            eq = (
                sum(1 for r in range(n_rounds) if strats[0][r] == B and strats[1][r] == B)
                / n_rounds
            )
            rows.append(
                {
                    "game_id": f"game_{g}",
                    "language": "en",
                    "n_rounds_is_known": True,
                    "max_rounds": n_rounds,
                    "played_rounds": n_rounds,
                    "agent1_name": "agent1",
                    "agent1_llm": "OpenAIGPT4o",
                    "agent1_personality": styles[0],
                    "agent1_strategies": strats[0],
                    "agent1_scores": s0,
                    "agent1_total_score": sum(s0),
                    "agent1_messages": [],
                    "agent2_name": "agent2",
                    "agent2_llm": "OpenAIGPT4o",
                    "agent2_personality": styles[1],
                    "agent2_strategies": strats[1],
                    "agent2_scores": s1,
                    "agent2_total_score": sum(s1),
                    "agent2_messages": [],
                    "welfare_sum": wsum,
                    "welfare_min": wmin,
                    "welfare_gini": round(wgini, 4),
                    "equilibrium_rate": round(eq, 4),
                }
            )
        # Native rows (lists stay lists), same shape a real run produces.
        _write_rows(run_dir, rows)
        (run_dir / "metadata.json").write_text(
            json.dumps(
                {
                    "id": sid,
                    "name": name,
                    "timestamp": (now - timedelta(hours=offset)).isoformat(timespec="seconds"),
                    "config": {
                        "name": name,
                        "languages": ["en"],
                        "nRounds": n_rounds,
                        "agents": {
                            "names": ["agent1", "agent2"],
                            "personalities": {"en": styles},
                            "llmServices": ["OpenAIGPT4o", "OpenAIGPT4o"],
                        },
                        "_synthetic": True,
                    },
                    "n_rows": len(rows),
                },
                indent=2,
            )
        )
    logger.info("Seeded %d synthetic demo runs under %s", len(scenarios), runs_dir)
