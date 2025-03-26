import unittest
from pathlib import Path

from src.io_managers.io_manager import IoManager
from src.fairgame_factory import FairGameFactory


class PayoffCalculator:
    """
    Encapsulates the logic for calculating numeric payoffs from a configuration
    and a list of user choices.

    Process:
      1. Map literal choices to internal strategy keys.
      2. Determine the combination name for the chosen strategies.
      3. Retrieve the corresponding weight keys for that combination.
      4. Convert the weight keys into their numeric payoff values.
    
    If any step in this chain fails, a default zero payoff is returned.
    """

    def __init__(self, config: dict):
        """
        Initialize the PayoffCalculator with a configuration containing
        a payoff matrix.

        Args:
            config (dict): A dictionary containing the entire game configuration.
        """
        self.payoff_matrix = config["payoffMatrix"]

    def _get_strategy_map(self) -> dict:
        """
        Reverse the 'strategies' mapping in the configuration.
        
        Returns:
            dict: A reverse mapping from literal representation to internal key.
                  For example, {"OptionA": "strategy1"}.
        """
        strategies = self.payoff_matrix["strategies"]["en"]
        return {literal: key for key, literal in strategies.items()}

    def _map_choices_to_strategies(self, choices: list) -> list:
        """
        Convert literal user choices to internal strategy keys.

        If any literal choice is unrecognized, return None.

        Args:
            choices (list): A list of choice strings made by the user.

        Returns:
            list|None: A list of corresponding strategy keys, or None if any
                       choice is invalid.
        """
        strategy_map = self._get_strategy_map()
        chosen_strategies = []
        for choice in choices:
            strategy_key = strategy_map.get(choice)
            if strategy_key is None:
                return None  # Invalid choice encountered
            chosen_strategies.append(strategy_key)
        return chosen_strategies

    def _find_combination_name(self, chosen_strategies: list) -> str:
        """
        Determine the combination name for the exact set of chosen strategy keys.

        Args:
            chosen_strategies (list): A list of valid internal strategy keys.

        Returns:
            str|None: The combination name (e.g., "combination1"), or None if
                      no exact match was found.
        """
        combinations = self.payoff_matrix["combinations"]
        for combo_name, combo_strategies in combinations.items():
            if combo_strategies == chosen_strategies:
                return combo_name
        return None

    def _get_weight_keys_for_combination(self, combination_name: str) -> list:
        """
        Retrieve the weight keys associated with a given combination name.

        Args:
            combination_name (str): The key for the combination in the matrix.

        Returns:
            list|None: A list of weight keys, or None if combination_name is invalid.
        """
        if not combination_name:
            return None
        return self.payoff_matrix["matrix"].get(combination_name, None)

    def _convert_weight_keys_to_payoffs(self, weight_keys: list) -> list:
        """
        Convert a list of weight keys into numeric payoff values.

        Args:
            weight_keys (list): A list of symbolic weight keys (e.g., ["w1", "w2"]).

        Returns:
            list|None: The numeric payoffs (e.g., [2, 3]) or None if keys are invalid.
        """
        if not weight_keys:
            return None
        weights = self.payoff_matrix["weights"]
        return [weights.get(key, 0) for key in weight_keys]

    def get_payoffs(self, choices: list) -> list:
        """
        High-level method to compute payoffs from user choices.

        Orchestrates the entire conversion:
          - Map literal choices to strategy keys.
          - Find the matching combination name.
          - Convert weight keys into numeric payoffs.

        If any step fails, return a list of zeros of the same length as choices.

        Args:
            choices (list): A list of literal choices made by the user.

        Returns:
            list: A list of integer payoffs corresponding to each choice.
        """
        chosen_strategies = self._map_choices_to_strategies(choices)
        if chosen_strategies is None:
            return [0] * len(choices)

        combination_name = self._find_combination_name(chosen_strategies)
        if combination_name is None:
            return [0] * len(choices)

        weight_keys = self._get_weight_keys_for_combination(combination_name)
        if weight_keys is None:
            return [0] * len(choices)

        payoffs = self._convert_weight_keys_to_payoffs(weight_keys)
        if payoffs is None:
            return [0] * len(choices)

        return payoffs


class TestMultiAgentConfigFile(unittest.TestCase):
    """
    Unit tests to verify:
      - The integrity of configuration files.
      - The correct behavior of game creation via FairGameFactory.
      - Payoff calculation consistency with actual game outcomes.
    """

    @classmethod
    def setUpClass(cls):
        """
        Set up class-level paths for configurations, ensuring all tests have
        consistent access to file locations.
        """
        cls.BASE_PATH = Path(__file__).resolve().parent
        cls.CONFIG_DIR = cls.BASE_PATH / 'config'
        cls.CONFIG_FILE_VOLUNTEER_DILEMMA = cls.CONFIG_DIR / 'volunteer_dilemma_one_game.json'
        cls.CONFIG_FILE_VOLUNTEER_DILEMMA_PERMUTATIONS = (
            cls.CONFIG_DIR / 'volunteer_dilemma_multiple_games.json'
        )

    def setUp(self):
        """
        Initialize IoManager and FairGameFactory before each test.
        """
        self.io_manager = IoManager(root_path=self.BASE_PATH)
        self.game_factory = FairGameFactory()

    def _load_and_validate_config(self, config_file: Path) -> dict:
        """
        Load a configuration file and validate it against expected schemas or rules.

        Args:
            config_file (Path): The path to the JSON configuration file.

        Returns:
            dict: The validated configuration.
        """
        config = self.io_manager.load_config(config_file)
        return self.io_manager.process_and_validate_configuration(config)

    def test_validate_config(self):
        """
        Check that the volunteer dilemma configuration contains a 'matrix' key
        within its payoff matrix. This indicates the presence of the fundamental
        payoff structure.
        """
        config = self._load_and_validate_config(self.CONFIG_FILE_VOLUNTEER_DILEMMA)
        self.assertIn('matrix', config['payoffMatrix'], 
                      msg="The 'payoffMatrix' must contain a 'matrix' key.")

    def test_create_one_game(self):
        """
        Ensure that when the configuration file specifies only one game,
        exactly one game is created by the FairGameFactory.
        """
        config = self._load_and_validate_config(self.CONFIG_FILE_VOLUNTEER_DILEMMA)
        games = self.game_factory.create_games(config)
        self.assertEqual(len(games), 1, 
                         msg="Expected exactly one game to be created.")

    def test_create_multiple_games(self):
        """
        Verify that a configuration supporting multiple permutations leads to
        the correct number of created games (e.g., 64).
        """
        config = self.io_manager.load_config(self.CONFIG_FILE_VOLUNTEER_DILEMMA_PERMUTATIONS)
        games = self.game_factory.create_games(config)
        self.assertEqual(len(games), 64, 
                         msg="Expected 64 games from the multiple-game configuration.")

    def test_run_single_game(self):
        """
        Execute a single game and verify that the computed payoffs from the
        PayoffCalculator match the recorded game scores.

        Steps:
          1. Load and validate the configuration.
          2. Create and run games, retrieving outcomes.
          3. Compare the actual round outcomes (scores/decisions) against
             PayoffCalculator's computed payoffs.
        """
        config = self._load_and_validate_config(self.CONFIG_FILE_VOLUNTEER_DILEMMA)
        outcomes = self.game_factory.create_and_run_games(config)

        # Extract outcomes from the first round of the first game (named 'game_0').
        round1_outcomes = outcomes['game_0']['history']['round_1']
        scores = [outcome['score'] for outcome in round1_outcomes]
        decisions = [outcome['strategy'] for outcome in round1_outcomes]

        # Use PayoffCalculator to derive expected payoffs.
        calculator = PayoffCalculator(config)
        calculated_payoffs = calculator.get_payoffs(decisions)

        # Validate that the game engine's recorded scores match the calculated payoffs.
        self.assertEqual(scores, calculated_payoffs,
                         msg="Recorded scores should match the calculated payoffs.")


if __name__ == '__main__':
    unittest.main()
