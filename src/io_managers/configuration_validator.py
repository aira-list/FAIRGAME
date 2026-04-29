from typing import Dict, List, Literal, Optional, Union
from pydantic import BaseModel, ValidationError, model_validator
from src.io_managers.payoff_matrix_transformer import PayoffMatrixTransformer


class TypesConfig(BaseModel):
    """Optional Bayesian-game type system.

    Each agent draws a private type from ``labels`` according to ``probs``.
    ``commonKnowledge`` controls whether the *distribution* (not the realised
    type) is shared across agents in their prompts.
    """

    labels: List[str]
    probs: Optional[List[float]] = None  # uniform if omitted
    commonKnowledge: bool = False

    @model_validator(mode="after")
    def validate_types(self) -> "TypesConfig":
        if not self.labels:
            raise ValueError("agents.types.labels must be non-empty.")
        if self.probs is not None:
            if len(self.probs) != len(self.labels):
                raise ValueError(
                    "agents.types.probs must have the same length as labels."
                )
            if any(p < 0 for p in self.probs):
                raise ValueError("agents.types.probs must be non-negative.")
            total = sum(self.probs)
            if total <= 0:
                raise ValueError("agents.types.probs must sum to a positive value.")
        return self


class AgentsConfig(BaseModel):
    names: List[str]
    personalities: Dict[str, List[str]]
    opponentPersonalityProb: Optional[List[float]] = None  # optional unless single-config mode
    allAgentPermutations: Optional[bool] = False  # injected from top-level
    types: Optional[TypesConfig] = None

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
                raise ValueError(
                    f"Personality list for '{lang}' must be non-empty."
                )

        return self


class ConfigModel(BaseModel):
    name: str
    nRounds: int
    nRoundsIsKnown: bool
    payoffMatrix: Dict
    allAgentPermutations: bool
    agents: AgentsConfig

    # LLM config: either single llm or per-agent llms (list or dict)
    llm: Optional[str] = None
    llms: Optional[Union[List[str], Dict[str, str]]] = None

    languages: List[str]
    stopGameWhen: List[str]
    agentsCommunicate: bool
    promptTemplate: Optional[Dict[str, str]] = None
    templateFilename: Optional[str] = None

    # Fake communication settings
    fakeCommunication: Optional[bool] = False
    fakeMessageCount: Optional[int] = 1
    fakeMessageBase: Optional[str] = "dec"  # "dec" or "hex"
    # fakeSeed removed: we no longer use deterministic seeding

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

    continuationProbability: Optional[float] = None
    """If set, after the first round each subsequent round is played only
    with this probability — supports indefinite-horizon games."""

    equilibria: Union[List[str], str] = []
    """Combination keys (e.g. ``"combination4"``) declared to be equilibria,
    OR the literal string ``"auto"`` to compute pure-strategy Nash
    equilibria via nashpy at validation time."""

    paretoOptimalSum: Optional[float] = None
    """Sum of payoffs at the Pareto-optimal outcome. When provided, the
    welfare analysis emits an efficiency ratio."""

    utilityTransform: Optional[Dict[str, object]] = None
    """``{"type": "CRRA"|"FehrSchmidt"|"identity", ...}`` — mapping from raw
    payoffs to agent utilities (see :mod:`src.utility`)."""

    mixedStrategies: bool = False
    """If true, the agent is asked for a probability distribution over
    strategies and the engine samples from it."""

    reputationWindow: Optional[int] = None
    """When set (>=1), per-opponent ``{coopRateN}`` and ``{reputationN}``
    placeholders average only the most recent N rounds. Strategy1 is
    treated as 'cooperate' by convention."""

    reputationApplies: bool = True
    """When False, the rolling-cooperation-rate placeholders are filled
    with ``n/a`` / ``unknown`` regardless of history. Set this to False
    for asymmetric coordination games (Battle of the Sexes), zero-sum
    games, and any scenario where strategy1 doesn't mean 'cooperate'."""

    seed: Optional[int] = None
    """Master seed for deterministic replay. ``None`` = nondeterministic."""

    seedCount: Optional[int] = None
    """When set (and >1), the experiment is repeated this many times with
    distinct child seeds; results are aggregated with confidence intervals."""

    seeds: Optional[List[int]] = None
    """Explicit list of seeds; takes precedence over ``seedCount``."""

    # ---- Tournaments ----------------------------------------------------
    tournament: Optional[Dict[str, object]] = None
    """``{"enabled": true, "mode": "round_robin", "symmetric": true}`` —
    when enabled and the agent pool has more than two members, run all
    pairwise games instead of one big multi-agent game."""

    # ---- Baselines ------------------------------------------------------
    baselineSemantics: Optional[Dict[str, str]] = None
    """``{"cooperate": "strategy1", "defect": "strategy2"}`` — tells the
    canonical strategy library which strategy keys to read as
    cooperation/defection."""

    @model_validator(mode="after")
    def _validate_game_theory_extensions(self) -> "ConfigModel":
        if not (0.0 < self.discountFactor <= 1.0):
            raise ValueError("discountFactor must lie in (0, 1].")
        if self.continuationProbability is not None and not (
            0.0 < self.continuationProbability <= 1.0
        ):
            raise ValueError("continuationProbability must lie in (0, 1] when set.")
        if self.seedCount is not None and self.seedCount < 1:
            raise ValueError("seedCount must be >= 1.")
        if self.seeds is not None and not all(isinstance(s, int) for s in self.seeds):
            raise ValueError("seeds must be a list of integers.")
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
                "When 'llms' is a dict, its keys must match agent names exactly: "
                f"{detail}."
            )

        if not all(isinstance(v, str) and v for v in self.llms.values()):
            raise ValueError("All values in 'llms' dict must be non-empty strings.")

    # ---- Languages ----
    def _validate_languages(self) -> None:
        if not self.languages or not all(isinstance(l, str) and l for l in self.languages):
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
            result["equilibria"] = compute_nash_equilibria(
                result["payoffMatrix"], language
            )

        return result

    def _attempt_payoff_transform(self, original_data: dict) -> ConfigModel:
        """Try to transform and re-validate the payoffMatrix if the first attempt failed."""
        try:
            transformed_config = PayoffMatrixTransformer.transform_payoff_input(original_data)
            config_model = self._parse_and_validate(transformed_config)
            PayoffMatrixTransformer.validate_payoff_matrix(config_model.payoffMatrix)
            return config_model
        except Exception as e:
            raise KeyError(f"payoffMatrix validation failed after transformation: {e}")

    def _parse_and_validate(self, data: dict) -> ConfigModel:
        """Helper to parse the configuration dict into a validated Pydantic model."""
        try:
            return ConfigModel(**data)
        except ValidationError as e:
            raise TypeError(f"Validation error:\n{e}")
