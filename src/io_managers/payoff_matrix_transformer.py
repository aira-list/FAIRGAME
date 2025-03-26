

class PayoffMatrixTransformer:
    """
    Handles transformation and validation of the payoffMatrix field.
    """

    REQUIRED_KEYS_PAYOFF_MATRIX = {
        "weights": dict,
        "strategies": dict,
        "combinations": dict,
        "matrix": dict,
    }

    @staticmethod
    def transform_payoff_input(config_data: dict) -> dict:
        """
        If the payoffMatrix does not have the required keys in correct structure,
        transform it to the necessary structure.
        """
        original_matrix = config_data["payoffMatrix"]
        updated_payoff_matrix = {
            "weights": original_matrix["weights"],
            "strategies": original_matrix["strategies"],
            "combinations": {},
            "matrix": {}
        }

        # Iterate over each combination to split pairs into strategies & weights.
        for comb_key, pairs in original_matrix["combinations"].items():
            strategies = [pair[0] for pair in pairs]  # Extract strategy
            weights = [pair[1] for pair in pairs]     # Extract weight

            updated_payoff_matrix["combinations"][comb_key] = strategies
            updated_payoff_matrix["matrix"][comb_key] = weights

        # Replace the original payoffMatrix in the input JSON with the updated structure.
        config_data["payoffMatrix"] = updated_payoff_matrix
        return config_data

    @staticmethod
    def validate_payoff_matrix(payoff_matrix: dict) -> None:
        """
        Validates that the payoffMatrix has all required keys of the correct type.
        Raises:
            KeyError: If a required key is missing.
            TypeError: If a key is present but of the wrong type.
        """
        missing_keys = []
        type_errors = []
        for key, expected_type in PayoffMatrixTransformer.REQUIRED_KEYS_PAYOFF_MATRIX.items():
            if key not in payoff_matrix:
                missing_keys.append(key)
            elif not isinstance(payoff_matrix[key], expected_type):
                type_errors.append((key, type(payoff_matrix[key]), expected_type))

        if missing_keys:
            raise KeyError(f"Missing keys in payoffMatrix: {', '.join(missing_keys)}")

        if type_errors:
            formatted_errors = ", ".join(
                f"{key} (found: {found}, expected: {expected})"
                for key, found, expected in type_errors
            )
            raise TypeError(f"Type errors in payoffMatrix: {formatted_errors}")