"""Pydantic request/response models shared across route modules."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# Upper bound on batch iterations so the engine fan-out can't be unbounded.
MAX_RUN_ITERATIONS = 100


class RunBody(BaseModel):
    """An inline configuration to run."""

    config: dict[str, Any] | None = None
    # Demo mode answers every LLM call with an offline deterministic fake (no
    # API keys, no charges). Defaults to false: a direct API/CLI client runs
    # real models unless it explicitly opts in. The web UI sends its Demo/Live
    # toggle on every run, so it is unaffected by this default.
    demo: bool = False


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
    # Model that performs the translation: a featured model name from
    # ``GET /api/llms`` (e.g. "GPT-4o"), or any other LiteLLM model string
    # prefixed with ``litellm:`` (e.g. "litellm:ollama/llama3"). When omitted,
    # the server's default (FAIRGAME_TRANSLATOR_MODEL) is used.
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
    # See RunBody.demo — defaults to real models; the web UI sends its toggle.
    demo: bool = False


class RunConfigOptions(BaseModel):
    """Optional body for ``POST /api/configurations/{id}/run`` — carries the
    ``demo`` flag in the JSON body, matching the other run endpoints (rather
    than as a query parameter)."""

    demo: bool = False
