import unittest
import logging
from pathlib import Path

from src.fairgame_factory import FairGameFactory
from src.io_managers.io_manager import IoManager
from src.fairgame import FairGame, PayoffMatrix

# Configure logging at the module level
logging.basicConfig(level=logging.INFO)

# Define directory and configuration paths
BASE_PATH = Path(__file__).resolve().parent
CONFIG_DIR = BASE_PATH / 'config'

# Configuration file paths
CONFIG_MAIN_FILE = CONFIG_DIR / 'prisoner_dilemma.json'
CONFIG_NO_PERMUTATIONS_FILE = CONFIG_DIR / 'prisoner_dilemma_all_permutations_false.json'
CONFIG_MALFORMED_FILE = CONFIG_DIR / 'prisoner_dilemma_no_template.json'

# Constants for game configuration
LANGUAGE_MODEL = 'OpenAIGPT4o'
GAME_SETTINGS = {
    'nRounds': 3,
    'nRoundsIsKnown': True,
    'Agent1': 'agent1',
    'Personality1': 'aggressive',
    'OpponentPersonalityProb1': 80,
    'Agent2': 'agent2',
    'Personality2': 'cooperative',
    'OpponentPersonalityProb2': 90,
    'LLM': LANGUAGE_MODEL,
    'stopGameWhen': ["combination1"]
}
LANGUAGE = 'en'


class TestGame(unittest.TestCase):
    """
    Unit tests for the FairGame functionality, focusing on:
      - Configuration loading and validation
      - Agent permutations
      - Prompt template creation
      - Payoff matrix integrity
      - Single round execution
    """

    def setUp(self):
        """
        Set up the test environment, including:
          - IoManager for configuration loading
          - FairGameFactory for creating games, agents, and prompts
          - A default configuration loaded from CONFIG_MAIN_FILE
        """
        self.io_manager = IoManager(root_path=str(BASE_PATH))
        self.game_factory = FairGameFactory()
        self.game_factory.set_io_manager(self.io_manager)

        self.config = self.game_factory.load_config(CONFIG_MAIN_FILE)
        self.payoff_matrix = self._create_payoff_matrix(LANGUAGE)
        self.prompt_template = self._create_prompt_template(LANGUAGE)
        self.agents_communicate = False

    def _create_payoff_matrix(self, language: str) -> PayoffMatrix:
        """
        Create and return a PayoffMatrix based on the loaded configuration.

        Args:
            language (str): The language key to reference in the configuration.

        Returns:
            PayoffMatrix: The initialized payoff matrix object.
        """
        payoff_config = self.config['payoffMatrix']
        return PayoffMatrix(payoff_config, language)

    def _create_prompt_template(self, language: str) -> dict:
        """
        Create a prompt template using the FairGameFactory.

        Args:
            language (str): The language for which to create a prompt template.

        Returns:
            dict: A dictionary-based prompt template.
        """
        return self.game_factory.build_prompt_template(self.config, language)

    def _create_agents(self) -> dict:
        """
        Instantiate and return agents based on default or test-specific settings.

        Returns:
            dict: A dictionary of agent instances keyed by agent name.
        """
        agents = self.game_factory.create_agents(GAME_SETTINGS)
        logging.info(f"Created agents: {agents}")
        return agents

    def _initialize_game(self, agents: dict) -> FairGame:
        """
        Initialize and return a FairGame instance with the provided agents.

        Args:
            agents (dict): A dictionary of agent instances.

        Returns:
            FairGame: A configured FairGame instance.
        """
        return FairGame(
            name='test_prisoner_dilemma',
            language=LANGUAGE,
            agents=agents,
            n_rounds=GAME_SETTINGS['nRounds'],
            n_rounds_known=GAME_SETTINGS['nRoundsIsKnown'],
            payoff_matrix_data=self.config['payoffMatrix'],
            prompt_template=self.prompt_template,
            stop_conditions=GAME_SETTINGS['stopGameWhen'],
            agents_communicate=self.agents_communicate
        )

    def _display_payoff_matrix(self, payoff_matrix: PayoffMatrix) -> None:
        """
        Print the payoff matrix in a formatted table for debugging purposes.

        Args:
            payoff_matrix (PayoffMatrix): The payoff matrix to display.
        """
        logging.info("Displaying payoff matrix...")
        strategy_names = list(payoff_matrix.strategies.values())
        cell_width = 10

        # Construct header row
        header_row = " " * cell_width + "|".join(s.center(cell_width) for s in strategy_names)
        logging.info(header_row)
        logging.info("-" * len(header_row))

        num_strategies = len(strategy_names)
        for i, strategy in enumerate(strategy_names):
            row_entries = []
            for j in range(num_strategies):
                matrix_key = f'combination{i * num_strategies + j + 1}'
                weight_keys = payoff_matrix.matrix[matrix_key]
                score_values = [payoff_matrix.weights[w] for w in weight_keys]
                row_entries.append(f"{score_values[0]}/{score_values[1]}".center(cell_width))
            row_content = strategy.ljust(cell_width) + "|".join(row_entries)
            logging.info(row_content)
            logging.info("-" * len(header_row))

    def test_all_agent_permutations(self):
        """
        Verify all agent permutation combinations are computed correctly
        by FairGameFactory's 'compute_all_game_configurations' method.
        """
        agent_permutations_df = self.game_factory.compute_all_game_configurations(
            LANGUAGE, self.config['agents'], LANGUAGE_MODEL
        )
        logging.info(f"Agent permutations:\n{agent_permutations_df}")
        num_combinations = len(agent_permutations_df)
        self.assertEqual(num_combinations, 4)

    def test_configuration_malformed(self):
        """
        Ensure that a malformed configuration raises a KeyError when processed.
        """
        malformed_config = self.io_manager.load_config(str(CONFIG_MALFORMED_FILE))
        with self.assertRaises(KeyError):
            self.io_manager.process_and_validate_configuration(malformed_config)

    def test_configuration_well_formed(self):
        """
        Verify that a well-formed configuration is processed correctly,
        resulting in exactly one agent configuration (no permutations).
        """
        config = self.io_manager.load_config(str(CONFIG_NO_PERMUTATIONS_FILE))
        self.io_manager.process_and_validate_configuration(config)
        agents_configuration_df = self.game_factory.compute_configuration(
            LANGUAGE, config['agents'], config['llm']
        )
        self.assertEqual(agents_configuration_df.shape[0], 1)

    def test_prompt_template_creation(self):
        """
        Test that the prompt template contains the expected top-level keys.
        """
        self.assertIn('intro', self.prompt_template)
        self.assertIn('opponentIntro', self.prompt_template)
        self.assertIn('gameLength', self.prompt_template)

    def test_payoff_matrix(self):
        """
        Test that the payoff matrix has the correct combinations, weights,
        and that the game integrates it properly.
        """
        # Basic sanity check on the payoff matrix structure
        num_keys = len(self.payoff_matrix.matrix_data)
        self.assertEqual(num_keys, 4, "Payoff matrix should have exactly 4 combinations.")

        agents = self._create_agents()
        game_instance = self._initialize_game(agents)

        # Optional debug display of the payoff matrix
        self._display_payoff_matrix(game_instance.payoff_matrix)

        # Validate payoff outcomes for each possible combination
        self.assertEqual(
            game_instance.payoff_matrix.get_weights_for_combination(['Betray', 'Betray']),
            (3, 3)
        )
        self.assertEqual(
            game_instance.payoff_matrix.get_weights_for_combination(['Betray', 'Cooperate']),
            (5, 0)
        )
        self.assertEqual(
            game_instance.payoff_matrix.get_weights_for_combination(['Cooperate', 'Betray']),
            (0, 5)
        )
        self.assertEqual(
            game_instance.payoff_matrix.get_weights_for_combination(['Cooperate', 'Cooperate']),
            (1, 1)
        )

    def test_create_agents(self):
        """
        Verify that the correct number of agents are created with the given settings.
        """
        agents = self._create_agents()
        self.assertEqual(len(agents), 2, "Exactly two agents should be created.")

    def test_run_round(self):
        """
        Test running a single round and verify that:
          - Agents' chosen strategies match their recorded strategies
          - Agents' scores match the payoff matrix outcome
        """
        agents = self._create_agents()
        game_instance = self._initialize_game(agents)
        game_instance.run_round()

        # Extract agent decisions from the first round history
        agent1_history = game_instance.history.all_rounds['round_1']['agent1']
        agent2_history = game_instance.history.all_rounds['round_1']['agent2']
        agent1_strategy = agent1_history['strategy']
        agent2_strategy = agent2_history['strategy']
        agent1_score = agent1_history['score']
        agent2_score = agent2_history['score']

        # Verify the recorded strategy matches the agent object’s last strategy
        self.assertEqual(
            agents['agent1'].strategies[-1],
            agent1_strategy,
            "Agent1's final strategy should match the round history."
        )
        self.assertEqual(
            agents['agent2'].strategies[-1],
            agent2_strategy,
            "Agent2's final strategy should match the round history."
        )

        # Verify the scores align with the payoff matrix
        self.assertEqual(
            game_instance.payoff_matrix.get_weights_for_combination([agent1_strategy, agent2_strategy]),
            (agent1_score, agent2_score),
            "Round scores should match the payoff matrix combination outcome."
        )


if __name__ == '__main__':
    unittest.main()
