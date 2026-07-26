"""Library service: template lookup + configuration-run resolution/execution.

Route modules (:mod:`web_api.routes.library`, :mod:`web_api.routes.run_configs`,
:mod:`web_api.routes.transfer`) stay thin HTTP adapters; the shared behavior —
resolving a stored configuration into runnable engine configs, attaching the
right template bodies, and executing one (variant, iteration) unit — lives
here so no route ever needs to import from another route.

Errors are raised as ``HTTPException`` because every caller is an HTTP
handler; the service is web_api-internal, not an engine API.
"""

from __future__ import annotations

import copy
from typing import Any

from fastapi import HTTPException

from src.utils.rng import combine_seed
from web_api.configurations_lib import ResolvedVariant, is_group, iter_resolved_variants
from web_api.engine import get_engine
from web_api.run_history import save_run
from web_api.storage import load_store, new_id


def find_template(
    templates: list[dict[str, Any]],
    game_type_id: str,
    variation: str,
    language: str,
    *,
    exclude_id: str | None = None,
) -> dict[str, Any] | None:
    """First non-archived template matching (game_type, variation, language).

    That triple is unique among non-archived templates — create's upsert,
    update's collision check, run-time attachment, and bundle import all
    resolve against it through this helper.
    """
    return next(
        (
            t
            for t in templates
            if t["game_type_id"] == game_type_id
            and t["variation"] == variation
            and t["language"] == language
            and not t.get("archived")
            and (exclude_id is None or t["id"] != exclude_id)
        ),
        None,
    )


# Baseline strategies never read a prompt (the runner calls
# ``baseline_strategy.choose()`` directly), but the engine still builds a
# prompt for every game. For a baseline-only configuration we attach this
# inert placeholder so a run needs no template at all.
BASELINE_PROMPT_PLACEHOLDER = (
    "(baseline game — agents act algorithmically; this prompt is never read)"
)


def is_baseline_only(engine_cfg: dict[str, Any]) -> bool:
    """True when every agent in the config is a baseline strategy.

    Mirrors the engine's own model resolution, which accepts models under
    the top-level ``llms`` (list/dict) or ``llm`` (single string) as well as
    the GUI's ``agents.llmServices``/``agents.llms`` — so a baseline-only
    config in any of those shapes is detected (and needs no template).
    """
    agents = engine_cfg.get("agents") or {}
    candidates = agents.get("llmServices") or agents.get("llms") or engine_cfg.get("llms")
    if isinstance(candidates, dict):
        models = list(candidates.values())
    elif isinstance(candidates, (list, tuple)):
        models = list(candidates)
    else:
        single = engine_cfg.get("llm")
        models = [single] if isinstance(single, str) else []
    if not models:
        return False
    return all(isinstance(m, str) and m.startswith("baseline:") for m in models)


def attach_template(
    item: dict[str, Any], display_name: str, engine_cfg: dict[str, Any]
) -> dict[str, Any]:
    """Look up the per-language template bodies and attach them to ``engine_cfg``.

    Raises 400 when a required (game_type, variation, lang) template is missing —
    except for baseline-only configurations, which need no template and get
    an inert placeholder instead.
    """
    if is_baseline_only(engine_cfg):
        langs = item.get("languages") or engine_cfg.get("languages") or ["en"]
        engine_cfg["name"] = display_name
        engine_cfg["languages"] = langs
        engine_cfg["promptTemplate"] = {lang: BASELINE_PROMPT_PLACEHOLDER for lang in langs}
        return engine_cfg

    templates = load_store("templates")
    body_by_lang: dict[str, str] = {}
    for lang in item["languages"]:
        match = find_template(templates, item["game_type_id"], item["variation"], lang)
        if match is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"No template for game_type={item['game_type_id']!r} "
                    f"variation={item['variation']!r} language={lang!r}. "
                    f"Add or AI-translate one in the Templates page first."
                ),
            )
        body_by_lang[lang] = match["body"]
    engine_cfg["name"] = display_name
    engine_cfg["languages"] = item["languages"]
    engine_cfg["promptTemplate"] = body_by_lang
    return engine_cfg


def resolve_one_variant(item: dict[str, Any], variant_name: str | None) -> ResolvedVariant:
    """Pick a single resolved variant from ``item``, template attached.

    For a leaf, ``variant_name`` is ignored. For a group, ``variant_name``
    must exactly match one variant's bare name; 400 otherwise. Selection is
    by the variant's own name — display names are presentation, never
    matched against.
    """
    resolved = list(iter_resolved_variants(item))
    if not is_group(item):
        variant = resolved[0]
        return variant._replace(config=attach_template(item, variant.display_name, variant.config))

    if not variant_name:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Configuration {item['id']!r} is a group; pass ?variant=<name>. "
                f"Available: {[v.variant_name for v in resolved]}"
            ),
        )
    chosen = next((v for v in resolved if v.variant_name == variant_name), None)
    if chosen is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Variant {variant_name!r} not found in {item['name']!r}. "
                f"Available: {[v.variant_name for v in resolved]}"
            ),
        )
    engine_cfg = chosen.config
    # Stamp the bare variant name on the engine config so it lands as a
    # row column in the Run results.
    engine_cfg["payoffVariantName"] = chosen.variant_name
    return chosen._replace(config=attach_template(item, chosen.display_name, engine_cfg))


def resolve_runnable_variants(item: dict[str, Any]) -> list[ResolvedVariant]:
    """All runnable units for a configuration, templates attached.

    A leaf yields one unit; a group yields one per payoff variant in
    declared order.
    """
    out: list[ResolvedVariant] = []
    for variant in iter_resolved_variants(item):
        engine_cfg = copy.deepcopy(variant.config)
        if is_group(item):
            engine_cfg["payoffVariantName"] = variant.variant_name
        out.append(variant._replace(config=attach_template(item, variant.display_name, engine_cfg)))
    return out


def run_variant_iteration(
    cid: str,
    item: dict[str, Any],
    variant: ResolvedVariant,
    it: int,
    iterations: int,
    progress_cb=None,
) -> dict[str, Any]:
    """Run one (variant, iteration) unit, persist it, and return its result row.

    Shared by ``run-batch`` and its streaming twin. Deep copy per iteration:
    the engine and ``save_run`` both retain ``cfg``; a shallow copy would
    share nested payoffMatrix/agents across iterations' saved metadata.

    Iteration 0 runs the configuration exactly as stored; every later
    iteration folds its index into the seed axis with ``combine_seed`` so
    independent iterations consume different randomness. Folding (rather than
    ``seed + it``) keeps the iteration axis from colliding with the
    ``seedCount`` sweep's ``base + i`` children, and an explicit ``seeds``
    list is re-derived per iteration instead of being ignored.
    """
    cfg = copy.deepcopy(variant.config)
    if it > 0:
        if cfg.get("seeds"):
            cfg["seeds"] = [combine_seed(int(s), it) for s in cfg["seeds"]]
        elif cfg.get("seed") is not None:
            cfg["seed"] = combine_seed(int(cfg["seed"]), it)
    rows = get_engine().create_and_run_games(cfg, progress_cb=progress_cb)
    run_id = new_id()
    save_run(run_id, cfg, rows, configuration_id=cid)
    row: dict[str, Any] = {
        "configuration_id": cid,
        "iteration": it + 1,
        "run_id": run_id,
        "n_rows": len(rows),
        "display_name": variant.display_name,
    }
    if is_group(item):
        row["variant"] = variant.variant_name
    return row
