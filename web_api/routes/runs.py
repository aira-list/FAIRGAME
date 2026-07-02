"""Run-management routes: /api/runs* + /api/compare."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from web_api import storage
from web_api.compare import build_comparison
from web_api.dashboards import build_dashboard
from web_api.engine import get_engine
from web_api.models import CompareModelsBody, RunBody
from web_api.run_history import list_runs, load_run, save_run

router = APIRouter()


@router.post("/api/runs")
def create_run(body: RunBody) -> dict[str, Any]:
    config = body.config
    if config is None:
        raise HTTPException(status_code=400, detail="Provide a 'config'.")

    try:
        rows = get_engine().create_and_run_games(config, demo=body.demo)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except TypeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    run_id = storage.new_id()
    save_run(run_id, config, rows, demo=body.demo)
    return {"id": run_id, "rows": rows}


@router.get("/api/runs")
def get_runs() -> dict[str, Any]:
    return {"runs": list_runs()}


@router.get("/api/runs/{run_id}")
def run_detail(run_id: str) -> dict[str, Any]:
    return load_run(run_id)


@router.get("/api/runs/{run_id}/dashboard")
def run_dashboard(run_id: str) -> dict[str, Any]:
    """Relevance-driven chart spec for one run (only charts its features warrant)."""
    if not storage.is_safe_segment(run_id):
        raise HTTPException(status_code=404, detail=f"Run {run_id!r} not found.")
    if not (storage.RUNS_DIR / run_id / "metadata.json").is_file():
        raise HTTPException(status_code=404, detail=f"Run {run_id!r} not found.")
    run = load_run(run_id)
    return build_dashboard(run.get("config", {}), run.get("rows", []))


@router.post("/api/compare")
def compare_models(body: CompareModelsBody) -> dict[str, Any]:
    """Cross-model comparison spec (robustness radar + multi-model charts)."""
    runs = []
    for rid in body.run_ids:
        # Unknown (or unsafe) ids are a client error — silently dropping
        # them would return an empty/partial comparison that masks the bug.
        if (
            not storage.is_safe_segment(rid)
            or not (storage.RUNS_DIR / rid / "metadata.json").is_file()
        ):
            raise HTTPException(status_code=404, detail=f"Run {rid!r} not found.")
        r = load_run(rid)
        runs.append({"config": r.get("config", {}), "rows": r.get("rows", [])})
    return build_comparison(runs)


@router.get("/api/runs/{run_id}/csv")
def run_csv(run_id: str) -> FileResponse:
    if not storage.is_safe_segment(run_id):
        raise HTTPException(status_code=404, detail=f"Run {run_id!r} not found.")
    csv_file = storage.RUNS_DIR / run_id / "results.csv"
    if not csv_file.is_file():
        raise HTTPException(status_code=404, detail=f"Run {run_id!r} not found.")
    return FileResponse(csv_file, media_type="text/csv", filename=f"fairgame_run_{run_id}.csv")
