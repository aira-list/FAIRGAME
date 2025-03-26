import itertools
import pandas as pd

from src.fairgame import FairGame
from src.agent import Agent
from src.io_managers.io_manager import IoManager


class FairGameFactory:
    """Factory class responsible for loading a configuration dictionary,
    generating agent/game permutations, creating FairGame instances, running
    games, and collecting output.

    Attributes:
        io_manager (IoManager): The I/O manager instance.
        config_all_langs_df (pd.DataFrame): DataFrame that stores all language configuration permutations.
        games (list): List of FairGame instances.
        output_dict (dict): Dictionary to store game results keyed by game number.
    """

    def __init__(self):
        """Initialize a new instance of FairGameFactory.

        Initializes:
            io_manager (IoManager): An instance of IoManager.
            config_all_langs_df (pd.DataFrame): An empty DataFrame for configuration data.
            games (list): An empty list to hold FairGame instances.
            output_dict (dict): An empty dictionary to store game output.
        """
        self.io_manager = IoManager()
        self.config_all_langs_df = pd.DataFrame()
        self.games = []
        self.output_dict = {}

    def _generate_language_config_df(self, config, lang):
        """Generate configuration DataFrame for a single language.

        Depending on the configuration, either computes all agent permutations
        or builds a single configuration.

        Args:
            config (dict): Configuration dictionary.
            lang (str): Language identifier.

        Returns:
            pd.DataFrame: A DataFrame containing the game configurations for the specified language.
        """
        if config["allAgentPermutations"]:
            return self.compute_all_game_configurations(
                lang,
                config['agents'],
                config['llm']
            )
        return self.compute_configuration(lang, config['agents'], config['llm'])

    def _compute_agent_configurations(self, lang, config_agents):
        """Generate all agent configurations including names, personality, and knowledge permutations.

        Computes all combinations of agent names, personalities, and opponent personality probabilities.

        Args:
            lang (str): Language identifier.
            config_agents (dict): Dictionary containing agent configurations with keys such as 'names',
                                  'personalities', and 'opponentPersonalityProb'.

        Returns:
            tuple: A tuple containing:
                - agent_combinations (list): List of agent name combinations.
                - personality_permutations (list): List of personality permutations.
                - knowledge_permutations (list): List of knowledge permutations.
        """
        n_agents = len(config_agents['names'])
        agent_combinations = [config_agents['names']]
        personality_permutations = list(
            itertools.product(config_agents['personalities'][lang], repeat=n_agents)
        )
        knowledge_permutations = list(
            itertools.product(config_agents['opponentPersonalityProb'], repeat=n_agents)
        )
        return (
            agent_combinations,
            personality_permutations,
            knowledge_permutations
        )

    def _generate_full_permutations(self, agent_combinations, personality_permutations, knowledge_permutations):
        """Generate full configuration permutations for agents.

        Constructs a DataFrame from all combinations of agents, personality permutations,
        and knowledge permutations.

        Args:
            agent_combinations (list): List of agent combinations.
            personality_permutations (list): List of personality tuples.
            knowledge_permutations (list): List of knowledge tuples.

        Returns:
            pd.DataFrame: DataFrame containing all possible game configuration permutations.
        """
        rows = []
        for agents in agent_combinations:
            n_agents = len(agents)
            for personality_tuple, knowledge_tuple in itertools.product(personality_permutations, knowledge_permutations):
                row_dict = {
                    **{f"Agent{i+1}": agents[i] for i in range(n_agents)},
                    **{f"Personality{i+1}": personality_tuple[i] for i in range(n_agents)},
                    **{f"OpponentPersonalityProb{i+1}": knowledge_tuple[i] for i in range(n_agents)}
                }
                rows.append(row_dict)
        return pd.DataFrame(rows)

    def compute_all_game_configurations(self, lang, config_agents, llm_service):
        """Create a DataFrame of all permutations for a given language and LLM service.

        Args:
            lang (str): Language identifier.
            config_agents (dict): Agent configuration dictionary.
            llm_service: The LLM service to be used.

        Returns:
            pd.DataFrame: DataFrame containing all game configurations.
        """
        agent_combinations, pers_perms, knowledge_perms = self._compute_agent_configurations(lang, config_agents)
        df = self._generate_full_permutations(agent_combinations, pers_perms, knowledge_perms)
        df['LLM'] = llm_service
        df['Language'] = lang
        return df

    def compute_configuration(self, lang, config_agents, llm_service):
        """Generate a single configuration DataFrame for the first configuration.

        Useful when not generating all permutations.

        Args:
            lang (str): Language identifier.
            config_agents (dict): Agent configuration dictionary.
            llm_service: The LLM service to be used.

        Returns:
            pd.DataFrame: A single-row DataFrame with the configuration.
        """
        n_agents = len(config_agents['names'])
        row_dict = {}
        for i in range(n_agents):
            row_dict[f"Agent{i+1}"] = config_agents['names'][i]
            row_dict[f"Personality{i+1}"] = config_agents['personalities'][lang][i]
            row_dict[f"OpponentPersonalityProb{i+1}"] = config_agents['opponentPersonalityProb'][i]
        row_dict["LLM"] = llm_service
        row_dict["Language"] = lang
        return pd.DataFrame([row_dict])

    def _create_single_game(self, config, game_config_row, payoff_matrix):
        """Instantiate a single FairGame based on a configuration row.

        Builds a prompt template, creates agents, and instantiates a FairGame.

        Args:
            config (dict): Configuration dictionary.
            game_config_row (pd.Series): A row from the game configuration DataFrame.
            payoff_matrix: The payoff matrix for the game.

        Returns:
            FairGame: A FairGame instance.
        """
        prompt_template = self.build_prompt_template(config, game_config_row['Language'])
        agents = self.create_agents(game_config_row)
        return FairGame(
            config['name'],
            game_config_row['Language'],
            agents,
            config['nRounds'],
            config['nRoundsIsKnown'],
            payoff_matrix,
            prompt_template,
            config['stopGameWhen'],
            config['agentsCommunicate']
        )

    def create_agents(self, game_config_row):
        """Create agents based on the configuration row.

        Dynamically creates Agent instances for each agent defined in the configuration.
        Expected columns in the row include: Agent1, Personality1, OpponentPersonalityProb1, etc.

        Args:
            game_config_row (pd.Series): A row from the game configuration DataFrame with agent details.

        Returns:
            dict: A dictionary of Agent instances keyed by agent names.
        """
        agents_dict = {}
        i = 1
        while f"Agent{i}" in game_config_row:
            agent_name = game_config_row[f"Agent{i}"]
            personality = game_config_row[f"Personality{i}"]
            knowledge = game_config_row[f"OpponentPersonalityProb{i}"]
            agents_dict[agent_name] = Agent(
                name=agent_name,
                llm_service=game_config_row['LLM'],
                personality=personality,
                opponent_personality_prob=knowledge
            )
            i += 1
        return agents_dict
    
    def _upload_output(self, game, game_history, game_n):
        """Store game result in the output dictionary.

        Removes the payoff matrix from the game description and saves both the
        game description and its history.

        Args:
            game (FairGame): The FairGame instance.
            game_history: The history object returned from running the game.
            game_n (int): The game number used as an incremental index.
        """
        # Remove payoff matrix from the output to keep it concise
        game.description.pop('payoff_matrix', None)
        self.output_dict[f'game_{game_n}'] = {
            'description': game.description,
            'history': game_history.describe()
        }
    
    def set_io_manager(self, manager):
        """Set a custom IoManager instance.

        Args:
            manager (IoManager): A custom IoManager instance.
        """
        self.io_manager = manager

    def results_games(self):
        """Retrieve game results.

        Returns:
            dict: Dictionary of game results.
        """
        return self.output_dict

    def all_game_configurations(self):
        """Get all game configurations.

        Returns:
            pd.DataFrame: DataFrame of all game configurations across languages.
        """
        return self.config_all_langs_df

    def load_config(self, config_filename):
        """Load configuration dictionary from a file using IoManager.

        Args:
            config_filename (str): The filename of the configuration file.

        Returns:
            dict: Loaded configuration dictionary.
        """
        return self.io_manager.load_config(config_filename)

    def create_games(self, config):
        """Create FairGame instances from the configuration dictionary.

        For each language in the configuration, generates game configurations,
        concatenates them, and instantiates a FairGame for each configuration row.

        Args:
            config (dict): The processed configuration dictionary.

        Returns:
            list: A list of FairGame instances.
        """
        for lang in config['languages']:
            config_df = self._generate_language_config_df(config, lang)
            self.config_all_langs_df = pd.concat(
                [self.config_all_langs_df, config_df],
                ignore_index=True
            )

        # Create FairGame instances
        self.games = [
            self._create_single_game(config, row, config['payoffMatrix'])
            for _, row in self.config_all_langs_df.iterrows()
        ]
        return self.games

    def games_info(self):
        """Get descriptions of all created games.

        Returns:
            list: List of textual descriptions for each FairGame.
        """
        return [game.description() for game in self.games]

    def run_games(self):
        """Execute all FairGame instances and capture their outputs.

        Runs each game, uploads the output, and prints progress.
        """
        print(f"RUNNING {len(self.games)} GAMES")
        for i, game in enumerate(self.games):
            print(f"Game {i}:")
            game_history = game.run()
            self._upload_output(game, game_history, i)
            print('Completed')

    def load_config_create_and_run_games(self, config_filename):
        """Convenience method to load config, create games, run them, and return results.

        Args:
            config_filename (str): Filename of the configuration file.

        Returns:
            dict: Dictionary containing results of all games.
        """
        config = self.load_config(config_filename)
        return self.create_and_run_games(config)

    def create_and_run_games(self, config):
        """Validate configuration, create games, execute them, and return results.

        Args:
            config (dict): The raw configuration dictionary.

        Returns:
            dict: Dictionary containing the game results.
        """
        processed_config = self.io_manager.process_and_validate_configuration(
            config
        )
        self.create_games(processed_config)
        self.run_games()
        return self.output_dict

    def build_prompt_template(self, config, lang):
        """Retrieve or load the prompt template for a specific language.

        Attempts to get the template directly from the configuration dictionary; if not found,
        loads it from a file using IoManager.

        Args:
            config (dict): Configuration dictionary.
            lang (str): Language identifier.

        Returns:
            str: The prompt template.
        """
        try:
            template = config['promptTemplate'][lang]
        except KeyError:
            template = self.io_manager.load_template(config['templateFilename'], lang)
        return template
