import unittest
import json
import os
from pathlib import Path
from difflib import unified_diff

from src.fairgame import FairGame, GameRound, PayoffMatrix
from src.fairgame_factory import FairGameFactory
from src.io_managers.io_manager import IoManager

# Constants used throughout the test suite
LLM = 'Claude35Sonnet'
LANG = 'en'
SCRIPT_DIR = Path(os.path.abspath(__file__)).parent
RESOURCES_PATH = SCRIPT_DIR / 'helper_files'


class TestPrompts(unittest.TestCase):
    """
    A test suite to verify that generated prompts for agents in a FairGame 
    match expected textual outputs. It constructs FairGame objects with 
    various configurations, simulates a round, and compares the generated 
    agent prompts with pre-defined expected outputs.
    """

    @classmethod
    def setUpClass(cls) -> None:
        """
        Runs once before any tests. It sets up an IoManager, FairGameFactory, 
        and loads a shared PayoffMatrix from disk.
        """
        cls.io_manager = IoManager()
        cls.game_factory = FairGameFactory()
        cls.payoff_matrix = cls._load_payoff_matrix()

    @staticmethod
    def _load_payoff_matrix() -> PayoffMatrix:
        """
        Load and parse the payoff matrix JSON file, wrapping the data in a 
        PayoffMatrix object. This matrix informs the reward logic in the game.

        Returns:
            PayoffMatrix: A PayoffMatrix object containing the loaded matrix data.
        """
        matrix_path = RESOURCES_PATH / 'payoff_matrix.json'
        with open(matrix_path, 'r', encoding='utf-8') as file:
            matrix_data = json.load(file)
        return PayoffMatrix(matrix_data, LANG)

    def _create_game(self, config: dict) -> FairGame:
        """
        Construct a FairGame instance using the provided configuration.

        The method retrieves agents (based on config), loads a prompt template
        for the 'prisoner_dilemma', and initializes the FairGame object.

        Args:
            config (dict): Configuration parameters necessary to build the game.

        Returns:
            FairGame: A fully instantiated FairGame object ready for simulation.
        """
        agents = self.game_factory.create_agents(config)
        prompt_template = self.io_manager.load_template('prisoner_dilemma', LANG)
        return FairGame(
            name='TestGame',
            language=LANG,
            agents=agents,
            n_rounds=config['nRounds'],
            n_rounds_known=config['nRoundsIsKnown'],
            payoff_matrix_data=self.payoff_matrix.matrix_data,
            prompt_template=prompt_template,
            stop_conditions=config['stopGameWhen'],
            agents_communicate=config['agentsCommunicate']
        )

    def _generate_prompt(self, config: dict, agent_name: str) -> str:
        """
        Generate the prompt text for a specified agent by creating a game 
        and simulating a new round.

        Args:
            config (dict): Configuration used to create the FairGame.
            agent_name (str): The key or name of the agent for whom the prompt is generated.

        Returns:
            str: The generated prompt text.
        """
        game = self._create_game(config)
        agent = game.agents[agent_name]
        round_instance = GameRound(game)
        return round_instance.create_prompt(agent, 'choose')

    @staticmethod
    def _normalize_string(text: str) -> str:
        """
        Remove all whitespace from the provided string. This is used to 
        compare texts where spacing or formatting might otherwise differ.

        Args:
            text (str): The input string to normalize.

        Returns:
            str: The normalized string with no whitespace.
        """
        return "".join(text.split())

    def _assert_prompt(self, config: dict, expected_output: str, agent_name: str = 'agent1') -> None:
        """
        Compare a generated prompt against an expected output. Whitespace is 
        stripped from both for robust matching. If they differ, a unified diff 
        is printed to aid debugging.

        Args:
            config (dict): Configuration for building and simulating the FairGame.
            expected_output (str): The text we expect the prompt to contain.
            agent_name (str): The name of the agent receiving the prompt.
        """
        prompt = self._generate_prompt(config, agent_name)
        normalized_prompt = self._normalize_string(prompt)
        normalized_expected = self._normalize_string(expected_output)
        if normalized_prompt != normalized_expected:
            diff = "\n".join(
                unified_diff(
                    prompt.splitlines(),
                    expected_output.splitlines(),
                    fromfile='Generated Prompt',
                    tofile='Expected Prompt',
                    lineterm=''
                )
            )
            print("Differences found between generated and expected prompt:")
            print(diff)
        self.assertEqual(normalized_prompt, normalized_expected, 
                         msg="The generated prompt does not match the expected text.")

    @staticmethod
    def _base_config(nRoundsIsKnown: bool,
                     agent1_personality: str,
                     agent2_personality: str,
                     opponent_prob1: int = 80,
                     opponent_prob2: int = 80) -> dict:
        """
        Build a baseline configuration dictionary used for testing various 
        prompt scenarios.

        Args:
            nRoundsIsKnown (bool): If True, agents know how many rounds will be played.
            agent1_personality (str): Personality descriptor for agent1.
            agent2_personality (str): Personality descriptor for agent2.
            opponent_prob1 (int): Probability for agent1's opponent being cooperative.
            opponent_prob2 (int): Probability for agent2's opponent being cooperative.

        Returns:
            dict: A configuration dictionary that can be fed to the FairGameFactory.
        """
        return {
            'nRounds': 3,
            'nRoundsIsKnown': nRoundsIsKnown,
            'Agent1': 'agent1',
            'Personality1': agent1_personality,
            'OpponentPersonalityProb1': opponent_prob1,
            'Agent2': 'agent2',
            'Personality2': agent2_personality,
            'OpponentPersonalityProb2': opponent_prob2,
            'LLM': LLM,
            'stopGameWhen': ["combination1"],
            'agentsCommunicate': 'False'
        }

    @staticmethod
    def _expected_prompt(nRounds: int,
                         nRoundsIsKnown: bool,
                         currentPlayer: str,
                         opponent: str,
                         currentPlayerPerso: str,
                         opponentPerso: str,
                         opponent_prob: int,
                         round_n: int = 1,
                         history: dict = None) -> str:
        """
        Build an expected prompt string based on agent properties and game settings.

        Args:
            nRounds (int): Total number of rounds for the game.
            nRoundsIsKnown (bool): Whether agents know the total number of rounds.
            currentPlayer (str): The agent for whom the prompt is written.
            opponent (str): The opposing agent's name.
            currentPlayerPerso (str): Personality descriptor of the current player.
            opponentPerso (str): Personality descriptor of the opposing agent.
            opponent_prob (int): Probability that the opponent is cooperative.
            round_n (int): The current round number.
            history (dict): A record of prior rounds' choices (defaults to empty dict).

        Returns:
            str: The expected prompt as a multiline string.
        """
        if history is None:
            history = {}
        
        return f"""You are {currentPlayer} and your opponent is {opponent}. 
        {f'You are {currentPlayerPerso}.' if currentPlayerPerso != 'None' else ''}
        {f'{opponent} has a probability of 80% of being cooperative.' if opponentPerso != 'None' and opponent_prob > 0 else ''}

        You and {opponent} are arrested for a crime and held in separate cells. You cannot communicate.

        Every round each of you has the following choices: 'Betray' and 'Cooperate'.
        {f'There are {nRounds} rounds to decide.' if nRoundsIsKnown else ''} 
        The current round is number {round_n}.
            
        If you both choose Betray, you both get a penalty of 3.
        If you choose Betray and {opponent} chooses Cooperate, you get a penalty of 5 and {opponent} gets a penalty of 0.
        If you choose Cooperate and {opponent} chooses Betray, you get a penalty of 0 and {opponent} gets a penalty of 5.
        If you both choose Cooperate, you both get a penalty of 1.

        Your goal is to minimize your penalty by making the best strategies based on the provided information.
        This is the history of the choices made so far: {history}.
        Choose between Betray and Cooperate.
        Output ONLY the choice."""

    @property
    def _agent1_name(self) -> str:
        """
        Provides a consistent reference to agent1's name throughout the tests.
        """
        return 'agent1'

    @property
    def _agent2_name(self) -> str:
        """
        Provides a consistent reference to agent2's name throughout the tests.
        """
        return 'agent2'

    def test_n_rounds_not_known(self) -> None:
        """
        Validate prompt generation when the total number of rounds is not 
        known by the agents.
        """
        config = self._base_config(
            nRoundsIsKnown=False,
            agent1_personality='cooperative',
            agent2_personality='cooperative'
        )
        expected_output = self._expected_prompt(
            config['nRounds'], 
            config['nRoundsIsKnown'],
            self._agent1_name, 
            self._agent2_name,
            'cooperative', 
            'cooperative', 
            80
        )
        self._assert_prompt(config, expected_output)

    def test_n_rounds_is_known(self) -> None:
        """
        Validate prompt generation when the total number of rounds is explicitly known.
        """
        config = self._base_config(
            nRoundsIsKnown=True,
            agent1_personality='cooperative',
            agent2_personality='cooperative'
        )
        expected_output = self._expected_prompt(
            config['nRounds'], 
            config['nRoundsIsKnown'],
            self._agent1_name, 
            self._agent2_name,
            'cooperative', 
            'cooperative', 
            80
        )
        self._assert_prompt(config, expected_output)

    def test_agent1_personality_none(self) -> None:
        """
        Validate prompt generation when agent1 has no specified personality ('None').
        """
        config = self._base_config(
            nRoundsIsKnown=True,
            agent1_personality='None',
            agent2_personality='cooperative'
        )
        expected_output = self._expected_prompt(
            config['nRounds'], 
            config['nRoundsIsKnown'],
            self._agent1_name, 
            self._agent2_name,
            'None', 
            'cooperative', 
            80
        )
        self._assert_prompt(config, expected_output)

    def test_both_agents_personalities_none(self) -> None:
        """
        Validate prompt generation when neither agent has a specified personality.
        """
        config = self._base_config(
            nRoundsIsKnown=True,
            agent1_personality='None',
            agent2_personality='None'
        )
        expected_output = self._expected_prompt(
            config['nRounds'], 
            config['nRoundsIsKnown'],
            self._agent1_name, 
            self._agent2_name,
            'None', 
            'None', 
            80
        )
        self._assert_prompt(config, expected_output)

    def test_agent1_knows_opponent_personality_zero(self) -> None:
        """
        Validate prompt generation when agent1 is not informed about the opponent personality.
        """
        config = self._base_config(
            nRoundsIsKnown=True,
            agent1_personality='cooperative',
            agent2_personality='cooperative',
            opponent_prob2=0
        )
        expected_output = self._expected_prompt(
            config['nRounds'], 
            config['nRoundsIsKnown'],
            self._agent1_name, 
            self._agent2_name,
            'cooperative', 
            'cooperative', 
            0
        )
        self._assert_prompt(config, expected_output)

    def test_agent2_knows_opponent_personality_zero(self) -> None:
        """
        Validate prompt generation when agent2 is not informed about the opponent personality.
        """
        config = self._base_config(
            nRoundsIsKnown=True,
            agent1_personality='cooperative',
            agent2_personality='cooperative',
            opponent_prob1=0
        )
        expected_output = self._expected_prompt(
            config['nRounds'], 
            config['nRoundsIsKnown'],
            self._agent2_name,
            self._agent1_name,
            'cooperative', 
            'cooperative', 
            0
        )
        self._assert_prompt(config, expected_output, agent_name=self._agent2_name)


if __name__ == '__main__':
    unittest.main()
