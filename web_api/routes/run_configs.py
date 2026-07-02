"""Configuration-run verbs: run one, run a batch, run a batch with SSE progress.

Thin HTTP adapters over :mod:`web_api.library_service`, which owns variant
resolution, template attachment, and per-iteration execution.
"""

from __future__ import annotations

import json
import queue
import threading
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.llm_connectors import demo_mode
from src.utils.logger import get_logger
from web_api.configurations_lib import is_group
from web_api.engine import get_engine
from web_api.library_service import (
    resolve_one_variant,
    resolve_runnable_variants,
    run_variant_iteration,
)
from web_api.models import RunConfigurationsBody
from web_api.run_history import save_run
from web_api.storage import load_store, new_id

logger = get_logger(__name__)

router = APIRouter()


@router.post("/api/configurations/{config_id}/run")
def run_one_configuration(
    config_id: str,
    variant: str | None = None,
    demo: bool = True,
) -> dict[str, Any]:
    items = load_store("configurations")
    item = next((i for i in items if i["id"] == config_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Configuration {config_id!r} not found.")
    resolved = resolve_one_variant(item, variant)
    try:
        with demo_mode(demo):
            rows = get_engine().create_and_run_games(resolved.config)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    run_id = new_id()
    save_run(run_id, resolved.config, rows, configuration_id=config_id)
    out: dict[str, Any] = {
        "id": run_id,
        "rows": rows,
        "configuration_id": config_id,
        "display_name": resolved.display_name,
    }
    if is_group(item):
        out["variant"] = resolved.variant_name
    return out


@router.post("/api/configurations/run-batch")
def run_configurations_batch(body: RunConfigurationsBody) -> dict[str, Any]:
    """Run each configuration ``iterations`` times. Groups fan out: each
    variant runs ``iterations`` times. Iteration index offsets the seed
    so independent iterations consume different randomness."""
    items = load_store("configurations")
    results: list[dict[str, Any]] = []
    iterations = max(1, body.iterations or 1)
    for cid in body.configuration_ids:
        item = next((i for i in items if i["id"] == cid), None)
        if item is None:
            results.append({"configuration_id": cid, "error": "not found"})
            continue
        # Each entry below is one runnable variant. For a leaf it's the
        # single config; for a group it's every variation in declared order.
        # Shares the expansion logic with the streaming endpoint.
        try:
            variants = resolve_runnable_variants(item)
        except HTTPException as exc:
            results.append({"configuration_id": cid, "error": exc.detail})
            continue
        except ValueError as exc:
            results.append({"configuration_id": cid, "error": str(exc)})
            continue
        for variant in variants:
            for it in range(iterations):
                try:
                    with demo_mode(body.demo):
                        row = run_variant_iteration(cid, item, variant, it, iterations)
                except Exception as exc:  # noqa: BLE001
                    # Record this iteration's failure and keep going — one bad
                    # iteration (e.g. a transient LLM/network error) must not
                    # abort the rest of the batch.
                    results.append(
                        {
                            "configuration_id": cid,
                            "iteration": it + 1,
                            "variant": variant.variant_name,
                            "error": str(exc),
                        }
                    )
                    continue
                results.append(row)
    return {"results": results}


@router.post("/api/configurations/run-batch/stream")
def run_configurations_batch_stream(body: RunConfigurationsBody) -> StreamingResponse:
    """Streaming twin of ``run-batch``: same work, but emits Server-Sent
    Events so the UI can show a reliable 0-100% progress bar.

    Event stream (one JSON object per ``data:`` line):

    * ``{"type":"start","total":N,"units":U}`` — N = total games across the
      whole batch (variants x iterations x permutations x seeds), known
      upfront by building the permutation sets without running them.
    * ``{"type":"progress","completed":c,"total":N,"name":...,"language":...,
      "iteration":i,"variant":v}`` — emitted after each game finishes.
    * ``{"type":"run", ...}`` — a Run finished and was persisted (same shape
      as a ``run-batch`` result row).
    * ``{"type":"done","results":[...]}`` — terminal success event.
    * ``{"type":"error","error":...}`` — terminal fatal event.
    """
    items = load_store("configurations")
    iterations = max(1, body.iterations or 1)
    events: queue.Queue[dict[str, Any] | None] = queue.Queue()
    # Set when the client disconnects (the SSE generator is closed); the
    # worker checks it between games and aborts so a long LLM run isn't left
    # executing — and billing — with nobody consuming the output.
    cancel_event = threading.Event()

    class _Cancelled(Exception):
        """Internal signal: the client went away; stop the run."""

    def worker() -> None:
        results: list[dict[str, Any]] = []
        try:
            # ---- Plan pass: resolve units and size the bar upfront. ----
            # units: (cid, item, resolved_variant, games_per_iteration)
            units: list[tuple] = []
            grand_total = 0
            for cid in body.configuration_ids:
                item = next((i for i in items if i["id"] == cid), None)
                if item is None:
                    results.append({"configuration_id": cid, "error": "not found"})
                    continue
                try:
                    variants = resolve_runnable_variants(item)
                except (HTTPException, ValueError) as exc:
                    detail = getattr(exc, "detail", None) or str(exc)
                    results.append({"configuration_id": cid, "error": detail})
                    continue
                for variant in variants:
                    try:
                        per_iter = get_engine().count_games(variant.config)
                    except (ValueError, TypeError) as exc:
                        results.append(
                            {
                                "configuration_id": cid,
                                "variant": variant.variant_name,
                                "error": str(exc),
                            }
                        )
                        continue
                    units.append((cid, item, variant, per_iter))
                    grand_total += per_iter * iterations

            events.put({"type": "start", "total": grand_total, "units": len(units) * iterations})

            # ---- Run pass: execute every unit, threading cumulative offset. ----
            offset = 0
            for cid, item, variant, per_iter in units:
                for it in range(iterations):
                    if cancel_event.is_set():
                        return  # client gone — stop before starting more work

                    def cb(
                        info: dict[str, Any],
                        _off: int = offset,
                        _it: int = it,
                        _variant: str | None = variant.variant_name,
                        _name: str = variant.display_name,
                    ) -> None:
                        # Abort the in-progress run at the next game boundary
                        # if the client has disconnected.
                        if cancel_event.is_set():
                            raise _Cancelled()
                        events.put(
                            {
                                "type": "progress",
                                "completed": _off + int(info["completed"]),
                                "total": grand_total,
                                "name": info.get("name"),
                                "language": info.get("language"),
                                "iteration": _it + 1,
                                "variant": _variant,
                                "config_name": _name,
                            }
                        )

                    try:
                        with demo_mode(body.demo):
                            row = run_variant_iteration(
                                cid, item, variant, it, iterations, progress_cb=cb
                            )
                    except _Cancelled:
                        return
                    except Exception as exc:  # noqa: BLE001
                        # Record this iteration's failure and continue — a
                        # transient LLM/network error must not abort the batch.
                        results.append(
                            {
                                "configuration_id": cid,
                                "iteration": it + 1,
                                "variant": variant.variant_name,
                                "error": str(exc),
                            }
                        )
                        offset += per_iter
                        continue

                    results.append(row)
                    events.put({"type": "run", **row})
                    offset += per_iter

            events.put({"type": "done", "results": results})
        except _Cancelled:
            return  # client disconnected; nothing more to emit
        except Exception as exc:  # noqa: BLE001 — surface any fatal error to the client
            logger.exception("run-batch stream failed")
            events.put({"type": "error", "error": str(exc), "results": results})
        finally:
            events.put(None)  # sentinel: closes the SSE generator

    threading.Thread(target=worker, daemon=True).start()

    def event_stream():
        try:
            while True:
                item = events.get()
                if item is None:
                    break
                yield f"data: {json.dumps(item)}\n\n"
        finally:
            # Generator closed (client disconnected or finished) — tell the
            # worker to stop so it doesn't keep running games unconsumed.
            cancel_event.set()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
