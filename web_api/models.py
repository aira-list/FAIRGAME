"""Pydantic request/response models shared across route modules."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, model_validator

# Upper bound on batch iterations so the engine fan-out can't be unbounded.
MAX_RUN_ITERATIONS = 100

_DEMO_RETIRED_MSG = (
    "The 'demo' field was removed: demo mode no longer exists and every run "
    "executes real provider models (billed). Remove 'demo' from the request "
    "to proceed."
)


class _RejectsRetiredDemo(BaseModel):
    """Old clients could send ``demo: true`` expecting a free offline run.

    Silently ignoring the field (Pydantic's default for unknown keys) would
    bill them for calls they explicitly opted out of — fail loudly instead.
    """

    @model_validator(mode="before")
    @classmethod
    def _reject_demo(cls, data: Any) -> Any:
        if isinstance(data, dict) and "demo" in data:
            raise ValueError(_DEMO_RETIRED_MSG)
        return data


class RunBody(_RejectsRetiredDemo):
    """An inline configuration to run."""

    config: dict[str, Any] | None = None


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
    time (currently only ``"payoffMatrix"`` is allowed — the Literal makes
    an unknown axis fail as a 422 at the boundary instead of a 500 when
    ``configurations_lib`` resolves it). ``value`` is the full replacement
    value for that field. ``name`` is the human-readable label appended to
    the group's name to form the resolved display name
    (``"<group> · <variant>"``).
    """

    axis: Literal["payoffMatrix"]
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

    @model_validator(mode="after")
    def _validate_variations(self) -> ImportBundle:
        """The configuration travels as a raw dict, so its group variations
        would bypass :class:`VariationEntry` — validate them here so a bad
        axis fails as 422 at the boundary instead of a 500 at resolve time."""
        for entry in self.configuration.get("variations") or []:
            try:
                VariationEntry.model_validate(entry)
            except ValidationError as exc:
                # Re-raise as ValueError — the sanctioned way to fail a
                # validator, which pydantic folds into the outer 422.
                raise ValueError(str(exc)) from exc
        return self


class RunConfigurationsBody(_RejectsRetiredDemo):
    """Batch payload for the Experiment page.

    The configuration owns its own seed, seedCount, agents, payoffs and
    rounds — anything that isn't ``iterations`` belongs there, not here.
    Each iteration beyond the first folds its index into the configuration's
    seed(s) via ``combine_seed`` so independent iterations actually differ
    when the engine consumes randomness (see ``run_variant_iteration``).
    """

    configuration_ids: list[str]
    iterations: int = Field(default=1, ge=1, le=MAX_RUN_ITERATIONS)
