
class PayoffMatrix:
    """
    Represents a payoff matrix with strategies and corresponding weights.

    This class is responsible for looking up valid strategies for the game,
    matching strategy keys to names, and applying the correct weights to each
    participant based on chosen strategies.
    """

    def __init__(self, matrix_data, language):
        """
        Initialize the PayoffMatrix with the given matrix data and language.

        Args:
            matrix_data (dict): A dictionary containing strategies, weights, matrix,
                                and combinations.
            language (str): The language key used to select the correct strategy names.
        """
        self.matrix_data = matrix_data
        self.language = language

    @property
    def strategies(self):
        """
        dict: The strategies available in the matrix for the given language.
        """
        return self.matrix_data['strategies'][self.language]
    
    @property
    def weights(self):
        """
        dict: The weight values keyed by weight labels.
        """
        return self.matrix_data['weights']
    
    @property
    def matrix(self):
        """
        dict: A mapping of combination keys to weight labels.
        """
        return self.matrix_data['matrix']
    
    def get_weights_for_combination(self, strategy_list):
        """
        Given a list of strategy names, return the corresponding tuple of weights
        for that exact combination.

        Args:
            strategy_list (list of str): The strategy names chosen by agents.

        Returns:
            tuple: A tuple of weight values corresponding to the chosen strategies.

        Raises:
            ValueError: If any strategy is invalid or if no matching combination is found.
        """
        name_to_key = {name: key for key, name in self.strategies.items()}
        key_list = []

        for strategy_name in strategy_list:
            strategy_key = name_to_key.get(strategy_name)
            if not strategy_key:
                raise ValueError(f"Invalid strategy: {strategy_name}")
            key_list.append(strategy_key)

        for combo_key, combo_strat_keys in self.matrix_data['combinations'].items():
            if combo_strat_keys == key_list:
                return tuple(self.weights[wk] for wk in self.matrix[combo_key])
        
        raise ValueError("No matching combination found.")

    def get_combination_key(self, round_strategies):
        """
        Return the key in the matrix that matches the given list of strategy keys.

        Args:
            round_strategies (list of str): Strategy keys (not names) selected for a round.

        Returns:
            str: The combination key in the matrix.

        Raises:
            ValueError: If the combination is not found in the matrix.
        """
        for combo_key, strat_keys in self.matrix_data['combinations'].items():
            if strat_keys == round_strategies:
                return combo_key
        raise ValueError("Combination not found.")
    
    def attribute_scores(self, agents, round_strategies):
        """
        Attribute scores to each agent based on the selected round strategies.

        Args:
            agents (list): A list of agent objects.
            round_strategies (list of str): Strategy keys (not names) for each agent.
        """
        combo_key = self.get_combination_key(round_strategies)
        weight_keys = list(self.matrix[combo_key])

        for agent in agents:
            if not weight_keys:
                break
            agent_weight = weight_keys.pop(0)
            agent.add_score(self.weights[agent_weight])