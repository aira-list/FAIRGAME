"""Populate the Results page with real runs of the starter-library seeds.

For every stored LLM-backed configuration (all seeds except the baseline-only
tournament, unless ``--configs`` narrows it), this script runs the engine
``--iterations`` times per model in ``--models``, overriding the agents'
models homogeneously (every agent plays the same model in a given run — the
standard FAIRGAME cross-model design, so the Compare view can group by model).
Each run goes through ``web_api.library_service.run_variant_iteration`` —
the same helper the web UI uses — so results attach to their configuration
and behave exactly like UI-started runs.

Usage (from the repo root, venv active, provider keys in ``.env``)::

    python tools/populate_seed_results.py --estimate   # count games/calls, run nothing
    python tools/populate_seed_results.py              # run 3 iterations x 3 models
    python tools/populate_seed_results.py --models "GPT-4o" --iterations 1
    python tools/populate_seed_results.py --configs seed_cfg_stag,seed_cfg_battle

A failed (config, model, iteration) unit is reported and skipped — one
transient provider error must not abort a long paid batch.
"""

from __future__ import annotations

import argparse
import copy
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.llm_connectors import MODEL_PROVIDER_MAP  # noqa: E402
from src.utils.logger import configure_logging, get_logger  # noqa: E402
from web_api.engine import get_engine  # noqa: E402
from web_api.library_service import (  # noqa: E402
    resolve_runnable_variants,
    run_variant_iteration,
)
from web_api.storage import load_store  # noqa: E402

logger = get_logger(__name__)

DEFAULT_MODELS = ["GPT-4o", "Claude Haiku 4.5"]


def _is_baseline(model: str) -> bool:
    # Case-insensitive like the engine's is_baseline_id: hand-written configs
    # use "Baseline:", the GUI emits "baseline:".
    return isinstance(model, str) and model.lower().startswith("baseline:")


def _llm_backed(item: dict[str, Any]) -> bool:
    """Whether any agent of the stored configuration is a real model.

    Mirrors the engine's model resolution (see
    ``web_api.library_service.is_baseline_only``): models may live under
    top-level ``llms`` (list/dict), single ``llm``, or the GUI's
    ``agents.llmServices``/``agents.llms`` shapes.
    """
    gc = item.get("game_config") or {}
    agents = gc.get("agents") or {}
    candidates = agents.get("llmServices") or agents.get("llms") or gc.get("llms")
    if isinstance(candidates, dict):
        models = list(candidates.values())
    elif isinstance(candidates, (list, tuple)):
        models = list(candidates)
    else:
        single = gc.get("llm")
        models = [single] if isinstance(single, str) else []
    return any(isinstance(m, str) and not _is_baseline(m) for m in models)


def _override_models(cfg: dict[str, Any], model: str) -> None:
    """Point every non-baseline agent at ``model`` (homogeneous self-play)."""
    llms = cfg.get("llms")
    if isinstance(llms, dict):
        cfg["llms"] = {k: (v if _is_baseline(v) else model) for k, v in llms.items()}
    elif isinstance(llms, (list, tuple)):
        cfg["llms"] = [(v if _is_baseline(v) else model) for v in llms]
    else:  # single-model 'llm' key
        cfg["llm"] = model


def _model_variant(variant, model: str):
    """A copy of ``variant`` with every non-baseline agent pointed at ``model``.

    The run itself (deepcopy per iteration, seed offset, engine call,
    persistence) is delegated to the canonical helper
    :func:`web_api.library_service.run_variant_iteration`, so runs produced
    here behave exactly like runs started from the web UI.
    """
    cfg = copy.deepcopy(variant.config)
    _override_models(cfg, model)
    cfg["name"] = f"{variant.display_name} · {model}"
    return variant._replace(config=cfg)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--models",
        default=",".join(DEFAULT_MODELS),
        help="Comma-separated model names (must exist in MODEL_PROVIDER_MAP).",
    )
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument(
        "--configs",
        default=None,
        help="Comma-separated configuration ids (default: every LLM-backed stored config).",
    )
    parser.add_argument(
        "--estimate",
        action="store_true",
        help="Only count games and approximate LLM calls; run nothing.",
    )
    args = parser.parse_args()
    configure_logging()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    unknown = [m for m in models if m not in MODEL_PROVIDER_MAP and not m.startswith("litellm:")]
    if unknown:
        parser.error(f"Unknown model name(s): {unknown}. See MODEL_PROVIDER_MAP.")

    items = load_store("configurations")
    if args.configs:
        wanted = {c.strip() for c in args.configs.split(",") if c.strip()}
        missing = wanted - {i["id"] for i in items}
        if missing:
            parser.error(f"Unknown configuration id(s): {sorted(missing)}")
        items = [i for i in items if i["id"] in wanted]
    else:
        items = [i for i in items if _llm_backed(i)]

    engine = get_engine()
    # Resolve each configuration's variants once; both passes reuse them.
    variants_by_item = {item["id"]: resolve_runnable_variants(item) for item in items}

    # ---- Estimate pass (always printed; --estimate stops after it) --------
    total_games = 0
    total_calls = 0
    print(f"{len(items)} configuration(s) x {len(models)} model(s) x {args.iterations} iteration(s)")
    for item in items:
        for variant in variants_by_item[item["id"]]:
            cfg = variant.config
            n_games = engine.count_games(cfg)
            rounds = int(cfg.get("nRounds") or 1)
            agents = len(((cfg.get("agents") or {}).get("names")) or [])
            per_iter_calls = n_games * rounds * agents
            games = n_games * len(models) * args.iterations
            calls = per_iter_calls * len(models) * args.iterations
            total_games += games
            total_calls += calls
            print(
                f"  {item['id']:<32} {variant.display_name[:44]:<46}"
                f" games={games:>4}  decisions>={calls:>5}"
            )
    print(
        f"TOTAL: {total_games} games, >= {total_calls} LLM decision calls"
        " (belief elicitation / ToM / trust monitoring add extra calls per round"
        " on the configs that enable them)"
    )
    if args.estimate:
        return 0

    # ---- Run pass ----------------------------------------------------------
    done, failed = 0, 0
    t0 = time.time()
    for item in items:
        for model in models:
            for variant in variants_by_item[item["id"]]:
                mv = _model_variant(variant, model)
                for it in range(args.iterations):
                    label = f"{variant.display_name} · {model} · iter {it + 1}"
                    try:
                        row = run_variant_iteration(item["id"], item, mv, it, args.iterations)
                        done += 1
                        print(f"[OK]   {label}  ->  run {row['run_id']} ({row['n_rows']} rows)")
                    except Exception as exc:  # noqa: BLE001 — keep the batch going
                        failed += 1
                        print(f"[FAIL] {label}  ->  {exc}")
    dt = time.time() - t0
    print(f"Finished: {done} run(s) saved, {failed} failed, in {dt / 60:.1f} min.")
    return 1 if failed and not done else 0


if __name__ == "__main__":
    sys.exit(main())
