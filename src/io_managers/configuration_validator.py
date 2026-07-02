from typing import Literal

from pydantic import BaseModel, Field, ValidationError, model_validator

from src.io_managers.payoff_matrix_transformer import PayoffMatrixTransformer


class TypesConfig(BaseModel):
    """Optional Bayesian-game type system.

    Each agent draws a private type from ``labels`` according to ``probs``.
    ``commonKnowledge`` controls whether the *distribution* (not the realised
    type) is shared across agents in their prompts.
    """

    labels: list[str]
    probs: list[float] | None = None  # uniform if omitted
    commonKnowledge: bool = False

    @model_validator(mode="after")
    def validate_types(self) -> "TypesConfig":
        if not self.labels:
            raise ValueError("agents.types.labels must be non-empty.")
        if self.probs is not None:
            if len(self.probs) != len(self.labels):
                raise ValueError("agents.types.probs must have the same length as labels.")
            if any(p < 0 for p in self.probs):
                raise ValueError("agents.types.probs must be non-negative.")
            total = sum(self.probs)
            if total <= 0:
                raise ValueError("agents.types.probs must sum to a positive value.")
        return self


class AgentsConfig(BaseModel):
    names: list[str]
    personalities: dict[str, list[str]]
    opponentPersonalityProb: list[float] | None = None  # optional unless single-config mode
    allAgentPermutations: bool | None = False  # injected from top-level
    types: TypesConfig | None = None

    @model_validator(mode="after")
    def validate_agents(self) -> "AgentsConfig":
        num_agents = len(self.names)

        if num_agents < 2:
            raise ValueError("There must be at least 2 agents.")

        # When ``allAgentPermutations`` is true the personality entries are a
        # *pool* to permute across, so they don't have to align 1:1 with the
        # agent count. The strict check is enforced in ConfigModel's
        # validator once the parent flag is known.
        for lang, plist in self.personalities.items():
            if not plist:
                raise ValueError(f"Personality list for '{lang}' must be non-empty.")

        return self


class ConfigModel(BaseModel):
    name: str
    nRounds: int
    nRoundsIsKnown: bool
    payoffMatrix: dict
    allAgentPermutations: bool = False
    agents: AgentsConfig

    # LLM config: either single llm or per-agent llms (list or dict)
    llm: str | None = None
    llms: list[str] | dict[str, str] | None = None

    languages: list[str]
    stopGameWhen: list[str] = Field(default_factory=list)
    agentsCommunicate: bool
    promptTemplate: dict[str, str] | None = None
    templateFilename: str | None = None

    # Fake communication settings
    fakeCommunication: bool | None = False
    fakeMessageCount: int | None = 1
    fakeMessageBase: str | None = "dec"  # "dec" or "hex"
    # fakeSeed removed: we no longer use deterministic seeding

    messageFormat: Literal["dec", "hex", "text"] | None = None
    """Expected shape of the *real* communication channel. ``"dec"``/``"hex"``
    force numeric-sequence extraction from replies (language-independent),
    ``"text"`` passes replies through verbatim, ``None`` = legacy English
    prompt-text sniffing (see ``src.game_round._extract_numeric_message``)."""

    # ---- Theory-of-Mind settings ------------------------------------
    elicitBeliefs: bool = False
    """When true, GameRound runs an extra ``believe`` phase that asks each
    agent to predict its opponent's strategy distribution."""

    tomOrder: Literal[0, 1, 2] = 1
    """ToM order injected into prompts:

    * 0 — opponent personality / prior is suppressed.
    * 1 — opponent personality / prior is shown (default; legacy behaviour).
    * 2 — additionally inject a ``{secondOrder}:[...]`` block, signalling
          that the opponent is also reasoning about the agent.
    """

    typesAreCommonKnowledge: bool = False
    """If types are configured and this flag is set, each agent's prompt is
    told the prior distribution over the *opponent's* type. The realised
    type stays private."""

    # ---- Game-theoretic extensions --------------------------------------
    discountFactor: float = 1.0
    """Per-round δ multiplier applied to attributed payoffs. Must be in (0, 1]."""

    discountMode: str = "score"
    """Where the discount acts. ``"score"`` (default, legacy) applies δ only
    when attributing payoffs — invisible to the agent. ``"prompt"`` instead
    describes the discount to the agent in the prompt (a ``{discount}`` block)
    so it shapes the LLM's *choices*, and does NOT touch the score (avoids
    counting the same preference as both treatment and measurement).
    ``"both"`` does prompt framing AND score attribution."""

    riskMode: str = "score"
    """Where a risk preference (CRRA utility transform) acts. ``"score"``
    (default) transforms attributed payoffs only. ``"prompt"`` instead
    describes risk aversion to the agent (a ``{riskFrame}`` block) so it
    shapes the LLM's choices, leaving the score untransformed. ``"both"``
    does both. Only meaningful when ``utilityTransform`` is CRRA; prompt-side
    fairness (Fehr-Schmidt) is not yet supported and falls back to score."""

    continuationProbability: float | None = None
    """If set, after the first round each subsequent round is played only
    with this probability — supports indefinite-horizon games."""

    equilibria: list[str] | str = []
    """Combination keys (e.g. ``"combination4"``) declared to be equilibria,
    OR the literal string ``"auto"`` to compute pure-strategy Nash
    equilibria via nashpy at validation time."""

    paretoOptimalSum: float | None = None
    """Sum of payoffs at the Pareto-optimal outcome. When provided, the
    welfare analysis emits an efficiency ratio."""

    utilityTransform: dict[str, object] | None = None
    """``{"type": "CRRA"|"FehrSchmidt"|"identity", ...}`` — mapping from raw
    payoffs to agent utilities (see :mod:`src.utility`)."""

    mixedStrategies: bool = False
    """If true, the agent is asked for a probability distribution over
    strategies and the engine samples from it."""

    reputationWindow: int | None = None
    """When set (>=1), per-opponent ``{coopRateN}`` and ``{reputationN}``
    placeholders average only the most recent N rounds. Strategy1 is
    treated as 'cooperate' by convention."""

    reputationApplies: bool = True
    """When False, the rolling-cooperation-rate placeholders are filled
    with ``n/a`` / ``unknown`` regardless of history. Set this to False
    for asymmetric coordination games (Battle of the Sexes), zero-sum
    games, and any scenario where strategy1 doesn't mean 'cooperate'."""

    seed: int | None = None
    """Master seed for deterministic replay. ``None`` = nondeterministic."""

    seedCount: int | None = None
    """When set (and >1), the experiment is repeated this many times with
    distinct child seeds; results are aggregated with confidence intervals."""

    seeds: list[int] | None = None
    """Explicit list of seeds; takes precedence over ``seedCount``."""

    payoffVariantName: str | None = None
    """Set by the run pipeline when this game came from one entry of a
    configuration group's ``variations`` list. Surfaces as the
    ``payoff_variant_name`` column in the per-game DataFrame so the
    Results page can compute sensitivity-to-payoff (the radar plot's
    S_P axis) for free."""

    # ---- Tournaments ----------------------------------------------------
    tournament: dict[str, object] | None = None
    """``{"enabled": true, "mode": "round_robin", "symmetric": true}`` —
    when enabled and the agent pool has more than two members, run all
    pairwise games instead of one big multi-agent game."""

    # ---- Baselines ------------------------------------------------------
    baselineSemantics: dict[str, str] | None = None
    """``{"cooperate": "strategy1", "defect": "strategy2"}`` — tells the
    canonical strategy library which strategy keys to read as
    cooperation/defection."""

    # ---- Trust / costly monitoring --------------------------------------
    trust: dict[str, object] | None = None
    """``{"enabled": true, "lookCost": 0.25, "historyScope": "full"}`` —
    enables a per-round monitoring decision (LOOK/NO_LOOK). Paying to LOOK
    reveals the opponent's history at the cost of ``lookCost`` points;
    NO_LOOK acts on trust with no information. See :class:`src.trust.TrustConfig`."""

    # ---- Agent interaction graph ----------------------------------------
    interaction: dict[str, object] | None = None
    """``{"directed": true, "default": "none"|"see"|"talk",
    "edges": [{"from": "a1", "to": "a2", "level": "talk"}]}`` — an explicit
    directed visibility + communication topology. An edge ``A -> B`` means
    B perceives A: ``see`` exposes A's plays to B, ``talk`` also delivers
    A's messages. Absent → the implicit complete graph (every agent
    perceives every other). See :class:`src.interaction.InteractionGraph`."""

    @model_validator(mode="after")
    def _validate_game_theory_extensions(self) -> "ConfigModel":
        if not (0.0 < self.discountFactor <= 1.0):
            raise ValueError("discountFactor must lie in (0, 1].")
        _modes = {"score", "prompt", "both"}
        if self.discountMode not in _modes:
            raise ValueError(f"discountMode must be one of {sorted(_modes)}.")
        if self.riskMode not in _modes:
            raise ValueError(f"riskMode must be one of {sorted(_modes)}.")
        if self.continuationProbability is not None and not (
            0.0 < self.continuationProbability <= 1.0
        ):
            raise ValueError("continuationProbability must lie in (0, 1] when set.")
        if self.seedCount is not None and self.seedCount < 1:
            raise ValueError("seedCount must be >= 1.")
        if self.seeds is not None and not all(isinstance(s, int) for s in self.seeds):
            raise ValueError("seeds must be a list of integers.")
        # Trust / interaction blocks: delegate to the domain constructors so
        # the validation rules exist in exactly one place (src.trust /
        # src.interaction) — this layer just surfaces their errors at
        # config-validation time instead of deep in game construction.
        from src.trust import TrustConfig

        if self.trust is not None:
            if not isinstance(self.trust, dict):
                raise ValueError("trust must be an object.")
            TrustConfig.from_config({"trust": self.trust})
        if self.interaction is not None:
            from src.interaction import InteractionGraph

            if not isinstance(self.interaction, dict):
                raise ValueError("interaction must be an object.")
            InteractionGraph.from_config({"interaction": self.interaction}, list(self.agents.names))
        return self

    # ------------- MAIN VALIDATOR (just orchestration) -------------
    @model_validator(mode="after")
    def validate_config(self) -> "ConfigModel":
        self._validate_prompt_source()
        self._inject_agent_flags()
        self._validate_opponent_probs()
        self._validate_llm_config()
        self._validate_languages()
        self._validate_fake_communication()
        return self

    # ------------- SMALL HELPERS BELOW -------------

    def _validate_prompt_source(self) -> None:
        """Exactly one of promptTemplate or templateFilename must be provided."""
        has_template_dict = bool(self.promptTemplate)
        has_template_file = bool(self.templateFilename)

        if has_template_dict == has_template_file:
            raise ValueError(
                "Exactly one of 'promptTemplate' or 'templateFilename' must be provided."
            )

    def _inject_agent_flags(self) -> None:
        """Propagate allAgentPermutations into the nested agents config."""
        self.agents.allAgentPermutations = self.allAgentPermutations

    def _validate_opponent_probs(self) -> None:
        """Validate ``opponentPersonalityProb`` and personalities length.

        Permutation semantics:

        * ``allAgentPermutations: false`` — both are 1:1 lists per agent.
        * ``allAgentPermutations: true`` — both are pools the factory permutes
          over; only required to be non-empty.
        """
        num_agents = len(self.agents.names)
        probs = self.agents.opponentPersonalityProb

        if self.allAgentPermutations:
            if not probs:
                raise ValueError(
                    "opponentPersonalityProb must be a non-empty list (used as the "
                    "permutation pool when allAgentPermutations=true)."
                )
            return

        if not probs or len(probs) != num_agents:
            raise ValueError("opponentPersonalityProb must match number of agents.")

        for lang, plist in self.agents.personalities.items():
            if len(plist) != num_agents:
                raise ValueError(
                    f"Personality list for '{lang}' must match number of agents "
                    f"({num_agents}) when allAgentPermutations=false."
                )

    # ---- LLM handling ----
    def _validate_llm_config(self) -> None:
        """Top-level dispatcher for LLM validation."""
        if self.llm is None and self.llms is None:
            raise ValueError("Provide either 'llm' (single string) or 'llms' (list or dict).")

        if self.llm is not None and self.llms is not None:
            raise ValueError("Provide only one of 'llm' or 'llms', not both.")

        if self.llm is not None:
            self._validate_single_llm()
        if self.llms is not None:
            self._validate_llms_collection()

    def _validate_single_llm(self) -> None:
        if not isinstance(self.llm, str) or not self.llm:
            raise ValueError("'llm' must be a non-empty string.")

    def _validate_llms_collection(self) -> None:
        num_agents = len(self.agents.names)

        if isinstance(self.llms, list):
            self._validate_llms_list(num_agents)
        elif isinstance(self.llms, dict):
            self._validate_llms_dict()
        else:
            raise ValueError(
                "'llms' must be either a list of strings or a dict of {agent_name: string}."
            )

    def _validate_llms_list(self, num_agents: int) -> None:
        if len(self.llms) != num_agents:
            raise ValueError(
                f"When 'llms' is a list, its length ({len(self.llms)}) "
                f"must equal number of agents ({num_agents})."
            )
        if not all(isinstance(x, str) and x for x in self.llms):
            raise ValueError("All entries in 'llms' list must be non-empty strings.")

    def _validate_llms_dict(self) -> None:
        agent_names_set = set(self.agents.names)
        llm_keys_set = set(self.llms.keys())

        if llm_keys_set != agent_names_set:
            missing = agent_names_set - llm_keys_set
            extra = llm_keys_set - agent_names_set
            parts = []
            if missing:
                parts.append(f"missing keys for agents {sorted(missing)}")
            if extra:
                parts.append(f"unexpected keys {sorted(extra)}")
            detail = "; ".join(parts) if parts else "mismatched keys"
            raise ValueError(
                f"When 'llms' is a dict, its keys must match agent names exactly: {detail}."
            )

        if not all(isinstance(v, str) and v for v in self.llms.values()):
            raise ValueError("All values in 'llms' dict must be non-empty strings.")

    # ---- Languages ----
    def _validate_languages(self) -> None:
        if not self.languages or not all(isinstance(lang, str) and lang for lang in self.languages):
            raise ValueError("'languages' must be a non-empty list of strings.")

    # ---- Fake communication ----
    def _validate_fake_communication(self) -> None:
        if not self.fakeCommunication:
            return

        if self.fakeMessageBase not in ("dec", "hex"):
            raise ValueError("fakeMessageBase must be either 'dec' or 'hex'.")

        if self.fakeMessageCount is None or self.fakeMessageCount <= 0:
            raise ValueError("fakeMessageCount must be a positive integer.")


class ConfigValidator:
    """
    Handles validation of top-level configuration data using Pydantic v2.
    """

    def validate_config_structure(self, config_data: dict) -> dict:
        """
        Parses and validates config_data using Pydantic.
        Attempts payoffMatrix transformation if initial validation fails.
        Raises:
            TypeError: if fields are missing or invalid.
            KeyError: if payoffMatrix is invalid even after transformation.
        """
        config_model = self._parse_and_validate(config_data)

        # Validate or transform payoffMatrix
        try:
            PayoffMatrixTransformer.validate_payoff_matrix(config_model.payoffMatrix)
        except KeyError:
            config_model = self._attempt_payoff_transform(config_data)

        result = config_model.model_dump()

        # Expand ``equilibria: "auto"`` now that the payoff matrix is
        # canonical. We do this here (post-validation) so we have the
        # transformed matrix to feed nashpy.
        if result.get("equilibria") == "auto":
            from src.equilibrium import compute_nash_equilibria  # local import

            language = (result.get("languages") or ["en"])[0]
            result["equilibria"] = compute_nash_equilibria(result["payoffMatrix"], language)

        return result

    def _attempt_payoff_transform(self, original_data: dict) -> ConfigModel:
        """Try to transform and re-validate the payoffMatrix if the first attempt failed."""
        import copy

        try:
            # Transform a copy: the transformer writes the expanded matrix
            # into its argument, and validation must not rewrite the caller's
            # config as a side effect.
            transformed_config = PayoffMatrixTransformer.transform_payoff_input(
                copy.deepcopy(original_data)
            )
            config_model = self._parse_and_validate(transformed_config)
            PayoffMatrixTransformer.validate_payoff_matrix(config_model.payoffMatrix)
            return config_model
        except TypeError:
            # Field-level validation failure (``_parse_and_validate`` maps
            # pydantic ValidationError -> TypeError). Preserve the type rather
            # than mislabeling it as a KeyError.
            raise
        except Exception as e:
            raise KeyError(f"payoffMatrix validation failed after transformation: {e}") from e

    def _parse_and_validate(self, data: dict) -> ConfigModel:
        """Helper to parse the configuration dict into a validated Pydantic model."""
        try:
            return ConfigModel(**data)
        except ValidationError as e:
            raise TypeError(f"Validation error:\n{e}") from e
