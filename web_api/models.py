"""Pydantic request/response models shared across route modules."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# Upper bound on batch iterations so the engine fan-out can't be unbounded.
MAX_RUN_ITERATIONS = 100


class RunBody(BaseModel):
    """An inline configuration to run."""

    config: dict[str, Any] | None = None
    # Demo mode answers every LLM call with an offline deterministic fake, so
    # runs need no API keys. On by default so the app is explorable out of the
    # box; send ``"demo": false`` to use real provider models (and keys).
    demo: bool = True


class HealthResponse(BaseModel):
    status: str
    message: str


class CompareModelsBody(BaseModel):
    """Cross-model comparison over a set of runs (grouped by model)."""

    run_ids: list[str]


class GameTypeBody(BaseModel):
    name: str
    description: str = ""


class TemplateBody(BaseModel):
    game_type_id: str
    variation: str
    language: str
    body: str
    source_template_id: str | None = None
    source_language: str | None = None


class TemplateTranslateBody(BaseModel):
    target_languages: list[str]
    # LiteLLM-resolvable model that performs the translation. When omitted the
    # server's default translator model (FAIRGAME_TRANSLATOR_MODEL) is used.
    model: str | None = None


class VariationEntry(BaseModel):
    """One axis value in a configuration group.

    ``axis`` names the engine field that this variation overrides at run
    time (currently only ``"payoffMatrix"`` is allowed). ``value`` is the
    full replacement value for that field. ``name`` is the human-readable
    label appended to the group's name to form the resolved display
    name (``"<group> · <variant>"``).
    """

    axis: str
    name: str
    value: Any


class ConfigurationBody(BaseModel):
    name: str
    game_type_id: str
    variation: str
    languages: list[str]
    game_config: dict[str, Any] = Field(default_factory=dict)
    # When non-empty, this configuration is a *group*: at run time the
    # engine receives one resolved leaf per entry. Leaves carry no
    # variations (or an empty list).
    variations: list[VariationEntry] | None = None


class ImportBundle(BaseModel):
    """A portable bundle exported from ``/api/configurations/{id}/export``:
    one configuration, the game type + templates it resolves against, and every
    related run (metadata + result rows). Imported via ``/api/import``."""

    fairgame_bundle: str
    configuration: dict[str, Any]
    game_type: dict[str, Any] | None = None
    templates: list[dict[str, Any]] = Field(default_factory=list)
    runs: list[dict[str, Any]] = Field(default_factory=list)


class RunConfigurationsBody(BaseModel):
    """Batch payload for the Experiment page.

    The configuration owns its own seed, seedCount, agents, payoffs and
    rounds — anything that isn't ``iterations`` belongs there, not here.
    Each iteration calls the engine with a fresh seed offset
    (``configuration.seed + iteration_index``) so independent
    iterations actually differ when the engine consumes randomness.
    """

    configuration_ids: list[str]
    iterations: int = Field(default=1, ge=1, le=MAX_RUN_ITERATIONS)
    # See RunBody.demo — on by default so batches run without API keys.
    demo: bool = True
