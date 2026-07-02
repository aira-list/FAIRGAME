"""Typed bundle of all per-game parameters — the engine's single declaration site.

Every per-game parameter is a dataclass field whose ``metadata`` says how it
is parsed from the raw camelCase input config (``raw`` key + optional
``coerce``) and how it is serialised into the game's description dict
(``desc`` key + emission policy). :meth:`from_raw` and :meth:`to_description`
are generic loops over that metadata, so adding a parameter means adding ONE
field here — its default, raw-config spelling, coercion, and description
spelling all live on that line. (The pydantic ``ConfigModel`` in
:mod:`src.io_managers.configuration_validator` still declares the field for
*untrusted-input* validation; that is a guard, not a second source of truth
for engine semantics.)

Field-name spellings across layers, for anyone tracing a value:

* raw input config — camelCase (``nRoundsIsKnown``), declared in ``raw=``.
* engine / this class — snake_case (``n_rounds_known``), the field name.
* description dict — historical keys (``number_of_rounds_is_known``),
  declared in ``desc=`` and exported as :class:`DescKey` constants so
  consumers (:mod:`src.results_processing.results_processor`) never hardcode
  them.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, fields
from typing import Any

from src.fake_message_generator import FakeCommunicationConfig
from src.trust import TrustConfig
from src.utility import IdentityTransform, UtilityTransform


class DescKey:
    """Description-dict key names (the game's serialisable summary).

    The description is produced by :meth:`GameConfig.to_description` (plus
    runtime additions in :attr:`FairGame.description`) and consumed by
    :mod:`src.results_processing.results_processor`. Import these constants
    instead of retyping the strings.
    """

    NAME = "name"
    LANGUAGE = "language"
    N_ROUNDS = "n_rounds"
    N_ROUNDS_IS_KNOWN = "number_of_rounds_is_known"
    AGENTS_COMMUNICATE = "agents_communicate"
    ELICIT_BELIEFS = "elicit_beliefs"
    TOM_ORDER = "tom_order"
    TYPES = "types"
    TYPES_COMMON_KNOWLEDGE = "types_common_knowledge"
    UTILITY_TRANSFORM = "utility_transform"
    DISCOUNT_FACTOR = "discount_factor"
    CONTINUATION_PROBABILITY = "continuation_probability"
    EQUILIBRIA = "equilibria"
    PARETO_OPTIMAL_SUM = "pareto_optimal_sum"
    MIXED_STRATEGIES = "mixed_strategies"
    REPUTATION_APPLIES = "reputation_applies"
    SEED = "seed"
    PAYOFF_VARIANT_NAME = "payoff_variant_name"
    FAKE_COMMUNICATION = "fake_communication"
    FAKE_MESSAGE_COUNT = "fake_message_count"
    FAKE_MESSAGE_BASE = "fake_message_base"
    TRUST = "trust"
    INTERACTION = "interaction"
    # Runtime-only keys added outside to_description:
    AGENTS = "agents"  # FairGame.description
    PAYOFF_MATRIX = "payoff_matrix"  # FairGame.description
    PAYOFF_MATRIX_SUMMARY = "payoff_matrix_summary"  # factory output enrichment


def _cfg(
    *,
    raw: str | None = None,
    coerce: Callable[[Any], Any] | None = None,
    coerce_always: bool = False,
    desc: str | None = None,
    desc_always: bool = False,
    desc_value: Callable[[Any], Any] | None = None,
    **field_kwargs: Any,
) -> Any:
    """Declare a config field with its parse/serialise metadata.

    * ``raw`` — key in the camelCase input config; ``None`` = supplied
      explicitly by the caller of :meth:`GameConfig.from_raw`.
    * ``coerce`` — applied to the raw value when present (``coerce_always``
      applies it even when absent, e.g. to build a default transform).
    * ``desc`` — key in the description dict; ``desc_always`` emits even
      when the value is empty/None, ``desc_value`` maps the value first.
    """
    return field(
        metadata={
            "raw": raw,
            "coerce": coerce,
            "coerce_always": coerce_always,
            "desc": desc,
            "desc_always": desc_always,
            "desc_value": desc_value,
        },
        **field_kwargs,
    )


def _build_utility(value: Any) -> UtilityTransform:
    from src.utility import build_utility_transform  # local: avoid cycle

    return build_utility_transform(value)


@dataclass
class GameConfig:
    """All per-game parameters in one validated object."""

    # ---- Required core ---------------------------------------------------
    name: str = _cfg(raw="name", desc=DescKey.NAME, desc_always=True)
    language: str = _cfg(desc=DescKey.LANGUAGE, desc_always=True)
    n_rounds: int = _cfg(raw="nRounds", coerce=int, desc=DescKey.N_ROUNDS, desc_always=True)
    n_rounds_known: bool = _cfg(
        raw="nRoundsIsKnown", coerce=bool, desc=DescKey.N_ROUNDS_IS_KNOWN, desc_always=True
    )
    payoff_matrix_data: dict[str, Any] = _cfg()
    prompt_template: str = _cfg()
    stop_conditions: list[str] = _cfg(raw="stopGameWhen", coerce=list)
    agents_communicate: bool = _cfg(
        raw="agentsCommunicate", coerce=bool, desc=DescKey.AGENTS_COMMUNICATE, desc_always=True
    )

    # ---- Theory of Mind --------------------------------------------------
    elicit_beliefs: bool = _cfg(
        raw="elicitBeliefs",
        coerce=bool,
        default=False,
        desc=DescKey.ELICIT_BELIEFS,
        desc_always=True,
    )
    tom_order: int = _cfg(
        raw="tomOrder", coerce=int, default=1, desc=DescKey.TOM_ORDER, desc_always=True
    )
    types_config: dict[str, Any] | None = _cfg(default=None)  # desc: paired, see to_description
    types_common_knowledge: bool = _cfg(raw="typesAreCommonKnowledge", coerce=bool, default=False)

    # ---- Game-theoretic extensions --------------------------------------
    utility_transform: UtilityTransform = _cfg(
        raw="utilityTransform",
        coerce=_build_utility,
        coerce_always=True,
        default_factory=IdentityTransform,
        desc=DescKey.UTILITY_TRANSFORM,
        desc_always=True,
        desc_value=lambda t: t.name,
    )
    discount_factor: float = _cfg(
        raw="discountFactor",
        coerce=float,
        default=1.0,
        desc=DescKey.DISCOUNT_FACTOR,
        desc_always=True,
    )
    # Where discount / risk preferences act: "score" (post-hoc lens, legacy),
    # "prompt" (described to the agent so it shapes choices, not the score),
    # or "both".
    discount_mode: str = _cfg(raw="discountMode", coerce=str, default="score")
    risk_mode: str = _cfg(raw="riskMode", coerce=str, default="score")
    continuation_probability: float | None = _cfg(
        raw="continuationProbability",
        default=None,
        desc=DescKey.CONTINUATION_PROBABILITY,
    )
    equilibria: Sequence[str] = _cfg(
        raw="equilibria",
        coerce=lambda v: list(v or []),
        default_factory=list,
        desc=DescKey.EQUILIBRIA,
    )
    pareto_optimal_sum: float | None = _cfg(
        raw="paretoOptimalSum", default=None, desc=DescKey.PARETO_OPTIMAL_SUM
    )
    mixed_strategies: bool = _cfg(
        raw="mixedStrategies",
        coerce=bool,
        default=False,
        desc=DescKey.MIXED_STRATEGIES,
        desc_always=True,
    )
    reputation_window: int | None = _cfg(raw="reputationWindow", default=None)
    reputation_applies: bool = _cfg(
        raw="reputationApplies",
        coerce=bool,
        default=True,
        desc=DescKey.REPUTATION_APPLIES,
        desc_always=True,
    )
    # Expected shape of the real-communication channel: "dec" / "hex" force
    # numeric-sequence extraction from replies, "text" passes replies through
    # verbatim, None = legacy prompt-text sniffing (English-only heuristic).
    message_format: str | None = _cfg(raw="messageFormat", default=None)
    # Which strategy keys count as cooperate/defect for baseline strategies.
    baseline_semantics: dict[str, str] | None = _cfg(raw="baselineSemantics", default=None)

    # ---- Collaborators (derived from the raw config, never post-assigned) --
    fake_communication_config: FakeCommunicationConfig = _cfg(
        default_factory=lambda: FakeCommunicationConfig(enabled=False)
    )
    trust_config: TrustConfig = _cfg(default_factory=lambda: TrustConfig(enabled=False))
    # InteractionGraph or None (None = implicit complete graph). Built by the
    # factory because it needs the per-game agent roster.
    interaction_graph: Any | None = _cfg(default=None)

    # ---- RNG -------------------------------------------------------------
    rng: random.Random | None = _cfg(default=None)
    seed: int | None = _cfg(default=None, desc=DescKey.SEED)

    # ---- Provenance ------------------------------------------------------
    payoff_variant_name: str | None = _cfg(
        raw="payoffVariantName", default=None, desc=DescKey.PAYOFF_VARIANT_NAME
    )

    @classmethod
    def from_raw(
        cls,
        raw: dict[str, Any],
        *,
        language: str,
        payoff_matrix_data: dict[str, Any],
        prompt_template: str,
        types_config: dict[str, Any] | None,
        rng: random.Random | None,
        seed: int | None,
        interaction_graph: Any | None = None,
    ) -> GameConfig:
        """Build a ``GameConfig`` from a validated raw input-config dict.

        Generic over the field metadata: every field with a ``raw`` key is
        read (and coerced) from ``raw``; absent/None values fall back to the
        field's declared default. The per-game collaborators the factory must
        compute first (resolved ``prompt_template``, ``types_config``,
        ``rng``/``seed``, ``interaction_graph``) are passed in explicitly.
        """
        kwargs: dict[str, Any] = {
            "language": language,
            "payoff_matrix_data": payoff_matrix_data,
            "prompt_template": prompt_template,
            "types_config": types_config,
            "rng": rng,
            "seed": seed,
            "interaction_graph": interaction_graph,
            "fake_communication_config": FakeCommunicationConfig.from_config(raw),
            "trust_config": TrustConfig.from_config(raw),
        }
        for f in fields(cls):
            raw_key = f.metadata.get("raw")
            if raw_key is None:
                continue
            coerce = f.metadata.get("coerce")
            if f.metadata.get("coerce_always"):
                kwargs[f.name] = coerce(raw.get(raw_key))
            elif raw_key in raw and raw[raw_key] is not None:
                value = raw[raw_key]
                kwargs[f.name] = coerce(value) if coerce else value
            # else: the dataclass default applies (required fields with no
            # default raise TypeError, matching the old KeyError contract).
        return cls(**kwargs)

    def __post_init__(self) -> None:
        if not (0.0 < self.discount_factor <= 1.0):
            raise ValueError(f"discount_factor must lie in (0, 1]; got {self.discount_factor}.")
        if self.continuation_probability is not None and not (
            0.0 < self.continuation_probability <= 1.0
        ):
            raise ValueError(
                "continuation_probability must lie in (0, 1] when set; "
                f"got {self.continuation_probability}."
            )
        if self.message_format is not None and self.message_format not in ("dec", "hex", "text"):
            raise ValueError(
                "message_format must be 'dec', 'hex' or 'text' when set; "
                f"got {self.message_format!r}."
            )

    def to_description(self) -> dict[str, Any]:
        """The config-derived portion of a game's serialisable description.

        Counterpart to :meth:`from_raw` and driven by the same field
        metadata; :attr:`FairGame.description` merges the runtime-only keys
        (agent info + the constructed payoff matrix). Optional fields are
        emitted only when set, matching the historical shape the results
        processor reads via :class:`DescKey`.
        """
        desc: dict[str, Any] = {}
        for f in fields(self):
            key = f.metadata.get("desc")
            if key is None:
                continue
            value = getattr(self, f.name)
            if not f.metadata.get("desc_always") and (value is None or value == []):
                continue
            mapper = f.metadata.get("desc_value")
            desc[key] = mapper(value) if mapper else value

        # Paired / structured blocks that a flat per-field policy can't express:
        if self.types_config is not None:
            desc[DescKey.TYPES] = self.types_config
            desc[DescKey.TYPES_COMMON_KNOWLEDGE] = self.types_common_knowledge
        fc = self.fake_communication_config
        desc[DescKey.FAKE_COMMUNICATION] = fc.enabled
        desc[DescKey.FAKE_MESSAGE_COUNT] = fc.message_count if fc.enabled else None
        desc[DescKey.FAKE_MESSAGE_BASE] = fc.base if fc.enabled else None
        if self.trust_config.enabled:
            desc[DescKey.TRUST] = {
                "enabled": True,
                "look_cost": self.trust_config.look_cost,
                "history_scope": self.trust_config.history_scope,
            }
        if self.interaction_graph is not None and not self.interaction_graph.is_fully_connected:
            desc[DescKey.INTERACTION] = self.interaction_graph.to_dict()
        return desc


#: Field names forwarded read-only by :class:`FairGame` (see its __getattr__).
CONFIG_FIELD_NAMES = frozenset(f.name for f in fields(GameConfig))
