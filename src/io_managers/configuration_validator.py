
from src.io_managers.payoff_matrix_transformer import PayoffMatrixTransformer

class ConfigValidator:
    """
    Handles validation of top-level configuration data.
    """

    REQUIRED_KEYS = {
        "name": str,
        "nRounds": int,
        "nRoundsIsKnown": bool,
        "payoffMatrix": dict,
        "allAgentPermutations": bool,
        "agents": dict,
        "llm": str,
        "languages": list,
        "stopGameWhen": list,
        "agentsCommunicate": bool
    }

    FILENAME_KEY = 'templateFilename'
    TEMPLATE_KEY = 'promptTemplate'

    def validate_config_structure(self, config_data: dict) -> dict:
        """
        Validates that the JSON data contains all required keys with correct types.
        Also checks if payoffMatrix is valid, and if not, tries to transform it.
        Raises:
            KeyError: If required keys are missing.
            TypeError: If any key is of the wrong type.
            KeyError: If the prompt template is misconfigured.
        """
        # Validate top-level keys
        self._check_keys(config_data, ConfigValidator.REQUIRED_KEYS)

        # Validate payoffMatrix structure (transform if needed)
        try:
            PayoffMatrixTransformer.validate_payoff_matrix(config_data["payoffMatrix"])
        except KeyError:
            # Attempt to transform payoffMatrix if missing required structure
            config_data = PayoffMatrixTransformer.transform_payoff_input(config_data)
            # Validate again
            PayoffMatrixTransformer.validate_payoff_matrix(config_data["payoffMatrix"])

        # Check template presence
        if not self._template_well_formed(config_data):
            raise KeyError(
                "Prompt template is not defined or is defined from different sources."
            )

        # Validate agent configuration if not all permutations are used
        if not config_data["allAgentPermutations"]:
            if not self._check_agents_configuration(config_data["agents"]):
                raise KeyError(
                    "Configuration error: There must be at least 2 agents and each agent's personalities "
                    "and the opponentPersonalityProb list must have a length equal to the number of agents."
                )

        return config_data

    def _check_keys(self, data: dict, required_keys: dict) -> None:
        """
        Ensures 'data' has all required keys of the correct type.
        Raises:
            KeyError: If any required key is missing.
            TypeError: If any required key is present but of the wrong type.
        """
        missing_keys = []
        type_errors = []
        for key, expected_type in required_keys.items():
            if key not in data:
                missing_keys.append(key)
            elif not isinstance(data[key], expected_type):
                type_errors.append((key, type(data[key]), expected_type))

        if missing_keys:
            raise KeyError(f"Missing keys: {', '.join(missing_keys)}")

        if type_errors:
            formatted_errors = ", ".join(
                f"{key} (found: {found}, expected: {expected})"
                for key, found, expected in type_errors
            )
            raise TypeError(f"Type errors: {formatted_errors}")

    def _template_well_formed(self, data: dict) -> bool:
        """
        Ensures we have exactly one of the two possible template definitions:
        'promptTemplate' or 'templateFilename'.
        """
        # XOR condition: Exactly one of them must be present.
        return (self.TEMPLATE_KEY in data) ^ (self.FILENAME_KEY in data)

    def _check_agents_configuration(self, agents_data: dict) -> bool:
        """
        Validates the agent configuration:
          - At least 2 agents are required.
          - The 'personalities' dict must have one key per agent.
          - Each agent's personality list must have length = total number of agents.
          - 'opponentPersonalityProb' must have length = total number of agents.
        """
        num_agents = len(agents_data.get("names", []))

        # Must have at least 2 agents
        if num_agents < 2:
            return False

        # Ensure each agent has a personality list that matches the number of agents
        personalities = agents_data.get("personalities", {})
        for _, v in personalities.items():
            if len(v) < 2:
                return False

        all_personalities_correct = all(
            len(personality_list) == num_agents
            for personality_list in personalities.values()
        )

        # Check that the opponentPersonalityProb list length matches the number of agents
        opponent_probs = agents_data.get("opponentPersonalityProb", [])
        opponent_probs_correct = len(opponent_probs) == num_agents if opponent_probs else False

        return all_personalities_correct and opponent_probs_correct