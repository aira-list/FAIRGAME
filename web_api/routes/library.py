"""Library CRUD: game types, templates (incl. AI-translate), configurations.

The run verbs live in :mod:`web_api.routes.run_configs`; shared resolution /
lookup behavior lives in :mod:`web_api.library_service`."""

from __future__ import annotations

import copy
from typing import Any

from fastapi import APIRouter, HTTPException

from src.utils.logger import get_logger
from web_api.configurations_lib import name_collisions
from web_api.engine import get_engine
from web_api.library_service import find_template
from web_api.models import (
    ConfigurationBody,
    GameTypeBody,
    TemplateBody,
    TemplateTranslateBody,
)
from web_api.storage import (
    edit_store,
    load_store,
    new_id,
    now_iso,
    record_deletion,
)

logger = get_logger(__name__)

router = APIRouter()


# ---- Game types ---------------------------------------------------------


@router.get("/api/game-types")
def list_game_types() -> dict[str, Any]:
    return {"game_types": load_store("game_types")}


@router.post("/api/game-types")
def create_game_type(body: GameTypeBody) -> dict[str, Any]:
    with edit_store("game_types") as game_types:
        if any(t["name"].lower() == body.name.lower() for t in game_types):
            raise HTTPException(status_code=409, detail=f"Game type {body.name!r} already exists.")
        game_type = {
            "id": new_id(),
            "name": body.name,
            "description": body.description,
            "created_at": now_iso(),
        }
        game_types.append(game_type)
    return game_type


@router.delete("/api/game-types/{game_type_id}")
def delete_game_type(game_type_id: str) -> dict[str, Any]:
    with edit_store("game_types") as game_types:
        if not any(t["id"] == game_type_id for t in game_types):
            raise HTTPException(status_code=404, detail=f"Game type {game_type_id!r} not found.")
        game_types[:] = [t for t in game_types if t["id"] != game_type_id]
        record_deletion("game_types", game_type_id)
        # Cascade: drop templates belonging to this game_type.
        with edit_store("templates") as templates:
            for t in templates:
                if t["game_type_id"] == game_type_id:
                    record_deletion("templates", t["id"])
            templates[:] = [t for t in templates if t["game_type_id"] != game_type_id]
    return {"deleted": game_type_id}


# ---- Templates ----------------------------------------------------------


@router.get("/api/templates")
def list_templates(
    game_type_id: str | None = None, include_archived: bool = False
) -> dict[str, Any]:
    items = load_store("templates")
    if game_type_id:
        items = [t for t in items if t["game_type_id"] == game_type_id]
    if not include_archived:
        items = [t for t in items if not t.get("archived")]
    return {"templates": items}


def _push_version(template: dict[str, Any]) -> None:
    """Snapshot the template's current body into its version history."""
    template.setdefault("versions", []).append(
        {
            "body": template.get("body", ""),
            "saved_at": template.get("updated_at") or template.get("created_at") or now_iso(),
        }
    )


def _new_template_record(
    *,
    game_type_id: str,
    variation: str,
    language: str,
    body: str,
    source_template_id: str | None = None,
    source_language: str | None = None,
) -> dict[str, Any]:
    """Build a fresh template record with the full, consistent field set.

    Single source of truth for the template shape so every creation path
    (manual create, upload, AI-translate) yields the same fields —
    ``versions``/``archived``/``updated_at`` included, which downstream code
    (archive/restore, version history) assumes exist.
    """
    now = now_iso()
    return {
        "id": new_id(),
        "game_type_id": game_type_id,
        "variation": variation,
        "language": language,
        "body": body,
        "source_template_id": source_template_id,
        "source_language": source_language,
        "created_at": now,
        "updated_at": now,
        "versions": [],
        "archived": False,
    }


@router.post("/api/templates")
def create_template(body: TemplateBody) -> dict[str, Any]:
    """Upsert a template by (game_type, variation, language).

    If a non-archived template already exists for that triple, its body is
    **overwritten** and the previous body is snapshotted into ``versions``;
    otherwise a new template is created. This single verb backs both "create
    new" and "upload overwrites" in the UI.
    """
    game_types = load_store("game_types")
    if not any(t["id"] == body.game_type_id for t in game_types):
        raise HTTPException(status_code=404, detail=f"Game type {body.game_type_id!r} not found.")
    with edit_store("templates") as templates:
        existing = find_template(templates, body.game_type_id, body.variation, body.language)
        if existing is not None:
            if existing.get("body", "") != body.body:
                _push_version(existing)
                existing["body"] = body.body
                existing["updated_at"] = now_iso()
            if body.source_template_id is not None:
                existing["source_template_id"] = body.source_template_id
            if body.source_language is not None:
                existing["source_language"] = body.source_language
            return existing

        template = _new_template_record(
            game_type_id=body.game_type_id,
            variation=body.variation,
            language=body.language,
            body=body.body,
            source_template_id=body.source_template_id,
            source_language=body.source_language,
        )
        templates.append(template)
    return template


@router.put("/api/templates/{template_id}")
def update_template(template_id: str, body: TemplateBody) -> dict[str, Any]:
    with edit_store("templates") as templates:
        # Reject a move onto another non-archived template's (game_type, variation,
        # language) triple — that triple must stay unique (create_template's
        # upsert and _attach_template's lookup both assume it), otherwise the
        # other template becomes an unreachable shadow.
        collision = find_template(
            templates,
            body.game_type_id,
            body.variation,
            body.language,
            exclude_id=template_id,
        )
        if collision is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"A template already exists for game_type={body.game_type_id!r} "
                    f"variation={body.variation!r} language={body.language!r}."
                ),
            )
        for t in templates:
            if t["id"] == template_id:
                if t.get("body", "") != body.body:
                    _push_version(t)
                    t["updated_at"] = now_iso()
                t["game_type_id"] = body.game_type_id
                t["variation"] = body.variation
                t["language"] = body.language
                t["body"] = body.body
                return t
    raise HTTPException(status_code=404, detail=f"Template {template_id!r} not found.")


@router.post("/api/templates/{template_id}/archive")
def archive_template(template_id: str) -> dict[str, Any]:
    with edit_store("templates") as templates:
        for t in templates:
            if t["id"] == template_id:
                t["archived"] = True
                t["archived_at"] = now_iso()
                return t
    raise HTTPException(status_code=404, detail=f"Template {template_id!r} not found.")


@router.post("/api/templates/{template_id}/restore")
def restore_template(template_id: str) -> dict[str, Any]:
    with edit_store("templates") as templates:
        for t in templates:
            if t["id"] == template_id:
                t["archived"] = False
                t.pop("archived_at", None)
                return t
    raise HTTPException(status_code=404, detail=f"Template {template_id!r} not found.")


@router.delete("/api/templates/{template_id}")
def delete_template(template_id: str) -> dict[str, Any]:
    """Permanent purge. The UI only offers this from the archived view;
    Archive (soft-delete) is the default destructive action."""
    with edit_store("templates") as templates:
        if not any(t["id"] == template_id for t in templates):
            raise HTTPException(status_code=404, detail=f"Template {template_id!r} not found.")
        templates[:] = [t for t in templates if t["id"] != template_id]
        record_deletion("templates", template_id)
    return {"deleted": template_id}


@router.post("/api/templates/{template_id}/translate")
def translate_template_into_languages(
    template_id: str, body: TemplateTranslateBody
) -> dict[str, Any]:
    """AI-translate one template into a list of target languages.

    Each successful translation becomes a *new* template under the same
    game_type and variation, with ``source_template_id`` linking back to the
    original. Skips a target if a template with the same (game_type, variation,
    language) already exists.
    """
    templates = load_store("templates")
    source = next((t for t in templates if t["id"] == template_id), None)
    if source is None:
        raise HTTPException(status_code=404, detail=f"Template {template_id!r} not found.")

    # Translate against a snapshot first — LLM calls are slow and must not
    # run while holding the store lock. The append below re-checks for
    # duplicates under the lock.
    created: list[dict[str, Any]] = []
    skipped: list[str] = []
    errors: list[dict[str, str]] = []
    for target in body.target_languages:
        if target == source["language"]:
            skipped.append(f"{target} (same as source)")
            continue
        already = any(
            t["game_type_id"] == source["game_type_id"]
            and t["variation"] == source["variation"]
            and t["language"] == target
            for t in templates
        )
        if already:
            skipped.append(f"{target} (already exists for this variation)")
            continue
        try:
            translated = get_engine().template_translator.translate(
                source["body"], target, cosine_threshold=body.cosine_threshold
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Translation to %s failed: %s", target, exc)
            errors.append({"language": target, "error": str(exc)})
            continue
        created.append(
            _new_template_record(
                game_type_id=source["game_type_id"],
                variation=source["variation"],
                language=target,
                body=translated,
                source_template_id=source["id"],
                source_language=source["language"],
            )
        )

    if created:
        with edit_store("templates") as current:
            still_new = []
            for tpl in created:
                dupe = any(
                    t["game_type_id"] == tpl["game_type_id"]
                    and t["variation"] == tpl["variation"]
                    and t["language"] == tpl["language"]
                    for t in current
                )
                if dupe:
                    skipped.append(f"{tpl['language']} (already exists for this variation)")
                else:
                    current.append(tpl)
                    still_new.append(tpl)
            created = still_new
    return {"created": created, "skipped": skipped, "errors": errors}


# ---- Configurations -----------------------------------------------------


@router.get("/api/configurations")
def list_configurations() -> dict[str, Any]:
    return {"configurations": load_store("configurations")}


def _serialize_body(body: ConfigurationBody, *, item_id: str) -> dict[str, Any]:
    """Project a Pydantic body into the on-disk dict shape."""
    item: dict[str, Any] = {
        "id": item_id,
        "name": body.name,
        "game_type_id": body.game_type_id,
        "variation": body.variation,
        "languages": body.languages,
        "game_config": body.game_config,
    }
    if body.variations:
        item["variations"] = [v.model_dump() for v in body.variations]
    return item


def _check_collisions(existing, candidate, *, exclude_id=None) -> None:
    bad = name_collisions(existing, candidate, exclude_id=exclude_id)
    if bad:
        sorted_names = sorted(bad)
        raise HTTPException(
            status_code=409,
            detail=(
                "Name collision; rename and try again. Conflicts: "
                + ", ".join(repr(n) for n in sorted_names)
            ),
        )


@router.post("/api/configurations")
def create_configuration(body: ConfigurationBody) -> dict[str, Any]:
    with edit_store("configurations") as items:
        item = _serialize_body(body, item_id=new_id())
        _check_collisions(items, item)
        item["created_at"] = now_iso()
        items.append(item)
    return item


@router.put("/api/configurations/{config_id}")
def update_configuration(config_id: str, body: ConfigurationBody) -> dict[str, Any]:
    with edit_store("configurations") as items:
        candidate = _serialize_body(body, item_id=config_id)
        _check_collisions(items, candidate, exclude_id=config_id)
        for item in items:
            if item["id"] == config_id:
                item.clear()
                item.update(candidate)
                item["created_at"] = item.get("created_at") or now_iso()
                return item
    raise HTTPException(status_code=404, detail=f"Configuration {config_id!r} not found.")


@router.delete("/api/configurations/{config_id}")
def delete_configuration(config_id: str) -> dict[str, Any]:
    with edit_store("configurations") as items:
        if not any(i["id"] == config_id for i in items):
            raise HTTPException(status_code=404, detail=f"Configuration {config_id!r} not found.")
        items[:] = [i for i in items if i["id"] != config_id]
        record_deletion("configurations", config_id)
    return {"deleted": config_id}


@router.post("/api/configurations/{config_id}/clone")
def clone_configuration(config_id: str) -> dict[str, Any]:
    """Duplicate a saved configuration. The clone keeps everything (including
    every variation in a group) and only its top-level ``name`` changes —
    ``" (copy)"`` is appended, with a ``" (copy N)"`` suffix when prior
    clones already occupy the default. Variants inside a group keep their
    own names; the resolved display names just reflect the new prefix."""
    with edit_store("configurations") as items:
        source = next((i for i in items if i["id"] == config_id), None)
        if source is None:
            raise HTTPException(status_code=404, detail=f"Configuration {config_id!r} not found.")

        clone = copy.deepcopy(source)
        clone["id"] = new_id()
        clone["created_at"] = now_iso()

        base = source["name"] + " (copy)"
        candidate_name = base
        n = 2
        while True:
            clone["name"] = candidate_name
            if not name_collisions(items, clone):
                break
            candidate_name = f"{base} {n}"
            n += 1

        items.append(clone)
    return clone
