from typing import Dict, List, Optional
from pydantic import BaseModel, ValidationError, model_validator
from src.io_managers.payoff_matrix_transformer import PayoffMatrixTransformer


class AgentsConfig(BaseModel):
    names: List[str]
    personalities: Dict[str, List[str]]
    opponentPersonalityProb: Optional[List[float]] = None  # Make it optional here
    allAgentPermutations: Optional[bool] = False  # Will be set later

    @model_validator(mode="after")
    def validate_agents(self) -> "AgentsConfig":
        num_agents = len(self.names)

        if num_agents < 2:
            raise ValueError("There must be at least 2 agents.")

        for agent_name, plist in self.personalities.items():
            if len(plist) != num_agents:
                raise ValueError(
                    f"Personality list for agent '{agent_name}' must match number of agents ({num_agents})."
                )

        return self


class ConfigModel(BaseModel):
    name: str
    nRounds: int
    nRoundsIsKnown: bool
    payoffMatrix: Dict
    allAgentPermutations: bool
    agents: AgentsConfig
    llm: str
    languages: List[str]
    stopGameWhen: List[str]
    agentsCommunicate: bool
    promptTemplate: Optional[Dict[str, str]] = None
    templateFilename: Optional[str] = None

    @model_validator(mode="after")
    def validate_config(self) -> "ConfigModel":
        if bool(self.promptTemplate) == bool(self.templateFilename):
            raise ValueError("Exactly one of 'promptTemplate' or 'templateFilename' must be provided.")

        # Inject allAgentPermutations into agents model
        self.agents.allAgentPermutations = self.allAgentPermutations

        # Validate opponentPersonalityProb only if needed
        num_agents = len(self.agents.names)
        if not self.allAgentPermutations:
            if not self.agents.opponentPersonalityProb or len(self.agents.opponentPersonalityProb) != num_agents:
                raise ValueError("opponentPersonalityProb must match number of agents.")

        return self


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
        print(config_data)  # Optional debug print
        config_model = self._parse_and_validate(config_data)

        # Validate or transform payoffMatrix
        try:
            PayoffMatrixTransformer.validate_payoff_matrix(config_model.payoffMatrix)
        except KeyError:
            try:
                transformed_config = PayoffMatrixTransformer.transform_payoff_input(config_data)
                config_model = self._parse_and_validate(transformed_config)
                PayoffMatrixTransformer.validate_payoff_matrix(config_model.payoffMatrix)
                config_data = config_model.model_dump()
            except Exception as e:
                raise KeyError(f"payoffMatrix validation failed after transformation: {e}")

        return config_model.model_dump()

    def _parse_and_validate(self, data: dict) -> ConfigModel:
        """
        Helper to parse the configuration dict into a validated Pydantic model.
        """
        try:
            return ConfigModel(**data)
        except ValidationError as e:
            raise TypeError(f"Validation error:\n{e}")
