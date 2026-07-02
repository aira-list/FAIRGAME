"""Portable export / import of a configuration together with its results.

A *bundle* (``fairgame_bundle`` JSON) is self-contained: the configuration,
the game_type + templates it resolves against, and every related run (metadata +
result rows). This lets a researcher move a configuration and the results it
produced between FAIRGAME instances, or archive/share them as a single file.

Export: ``GET  /api/configurations/{id}/export`` → downloadable JSON.
Import: ``POST /api/import``                     → recreates everything here.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from src.utils.logger import get_logger
from web_api.configurations_lib import name_collisions
from web_api.library_service import find_template
from web_api.models import ImportBundle
from web_api.run_history import import_run, runs_for_configuration
from web_api.storage import edit_store, load_store, new_id, now_iso

logger = get_logger(__name__)

router = APIRouter()

BUNDLE_VERSION = "1"


def _slug(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").lower()
    return s or "configuration"


@router.get("/api/configurations/{config_id}/export")
def export_configuration(config_id: str) -> JSONResponse:
    """Bundle a configuration + its game_type/templates + related runs as a file."""
    item = next((c for c in load_store("configurations") if c["id"] == config_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Configuration {config_id!r} not found.")

    game_type = next(
        (t for t in load_store("game_types") if t["id"] == item.get("game_type_id")), None
    )
    templates = [
        t
        for t in load_store("templates")
        if t.get("game_type_id") == item.get("game_type_id")
        and t.get("variation") == item.get("variation")
    ]
    runs = runs_for_configuration(config_id)

    bundle = {
        "fairgame_bundle": BUNDLE_VERSION,
        "exported_at": now_iso(),
        "configuration": item,
        "game_type": game_type,
        "templates": templates,
        "runs": runs,
    }
    filename = f"fairgame_{_slug(item.get('name', ''))}.fgbundle.json"
    return JSONResponse(
        bundle,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _resolve_game_type(
    bundle_game_type: dict[str, Any] | None, fallback_game_type_id: str | None
) -> str | None:
    """Ensure the bundle's game_type exists locally; return the resolved game_type id.

    Matches an existing game_type by name (so re-importing doesn't duplicate it);
    otherwise creates it, minting a fresh id on any id collision.
    """
    if not bundle_game_type:
        return fallback_game_type_id
    with edit_store("game_types") as game_types:
        existing = next(
            (t for t in game_types if t.get("name") == bundle_game_type.get("name")), None
        )
        if existing:
            return existing["id"]
        new_game_type = dict(bundle_game_type)
        if not new_game_type.get("id") or any(t["id"] == new_game_type["id"] for t in game_types):
            new_game_type["id"] = new_id()
        new_game_type.setdefault("description", "")
        new_game_type.setdefault("created_at", now_iso())
        game_types.append(new_game_type)
    return new_game_type["id"]


def _import_templates(bundle_templates: list[dict[str, Any]], game_type_id: str | None) -> int:
    """Add any bundle templates not already present for (game_type, variation, lang)."""
    added = 0
    with edit_store("templates") as templates:
        for tpl in bundle_templates:
            t = dict(tpl)
            t["game_type_id"] = game_type_id
            # Only a *non-archived* local template counts as "already present":
            # an archived one is invisible to the configuration-run template
            # lookup, so letting it shadow the bundle's template would leave
            # the imported configuration unrunnable.
            if (
                find_template(templates, game_type_id, t.get("variation"), t.get("language"))
                is not None
            ):
                continue
            if not t.get("id") or any(e["id"] == t["id"] for e in templates):
                t["id"] = new_id()
            t.setdefault("source_template_id", None)
            t.setdefault("source_language", None)
            t.setdefault("created_at", now_iso())
            templates.append(t)
            added += 1
    return added


def _unique_name(existing: list[dict[str, Any]], candidate: dict[str, Any]) -> str:
    """A library-unique name, suffixing ``(imported)`` on collision."""
    base = candidate.get("name") or "Imported configuration"
    name = base
    attempt = 0
    while name_collisions(existing, {**candidate, "name": name}):
        attempt += 1
        name = f"{base} (imported)" if attempt == 1 else f"{base} (imported {attempt})"
    return name


@router.post("/api/import")
def import_bundle(bundle: ImportBundle) -> dict[str, Any]:
    """Recreate a configuration (+ game_type, templates, runs) from a bundle.

    The configuration always gets a fresh id and a collision-safe name, so
    importing never overwrites existing library entries. Runs are recreated
    under fresh ids and re-linked to the new configuration.
    """
    if bundle.fairgame_bundle != BUNDLE_VERSION:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported bundle version {bundle.fairgame_bundle!r}; "
                f"expected {BUNDLE_VERSION!r}."
            ),
        )
    cfg = dict(bundle.configuration)
    if not cfg.get("game_config"):
        raise HTTPException(status_code=400, detail="Bundle configuration has no game_config.")

    # 1. Game type + templates so the imported config can actually run.
    game_type_id = _resolve_game_type(bundle.game_type, cfg.get("game_type_id"))
    cfg["game_type_id"] = game_type_id
    added_templates = _import_templates(bundle.templates, game_type_id)

    # 2. The configuration itself — fresh id, collision-safe name.
    with edit_store("configurations") as configs:
        cfg["id"] = new_id()
        cfg["name"] = _unique_name(configs, cfg)
        cfg["created_at"] = now_iso()
        configs.append(cfg)

    # 3. Related runs — fresh ids, re-linked to the new configuration.
    imported_runs = 0
    skipped_runs = 0
    for run in bundle.runs:
        run = dict(run)
        rows = run.pop("rows", [])
        if not isinstance(rows, list):
            skipped_runs += 1
            continue
        meta = dict(run)
        new_run_id = new_id()
        meta["id"] = new_run_id
        meta["configuration_id"] = cfg["id"]
        meta["n_rows"] = len(rows)
        import_run(new_run_id, meta, rows)
        imported_runs += 1

    return {
        "configuration": cfg,
        "imported_runs": imported_runs,
        "skipped_runs": skipped_runs,
        "added_templates": added_templates,
        "game_type_id": game_type_id,
    }
