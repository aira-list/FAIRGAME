from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import logging

from src.results_processing.game_data import GameData
from src.results_processing.agent_info import AgentInfo

logger = logging.getLogger(__name__)

class ResultsProcessor:
    """
    Processes game results and converts them into structured GameData objects and pandas DataFrames.
    """

    def aggregate_game_data(self, games_dict: Dict[str, Dict[str, Any]]) -> List[GameData]:
        """
        Aggregates data from multiple games into a list of GameData objects.

        Args:
            games_dict (Dict[str, Dict[str, Any]]):
                A dictionary keyed by game ID, where each value contains
                'description' and 'history' data.

        Returns:
            List[GameData]: A list of GameData objects, each representing a single game.
        """
        game_data_list = []
        for game_id, game_details in games_dict.items():
            game_data = self._process_single_game(game_id, game_details)
            if game_data:
                game_data_list.append(game_data)
        return game_data_list

    def process(self, games_dict: Dict[str, Dict[str, Any]]) -> pd.DataFrame:
        """
        Converts aggregated game data into a pandas DataFrame.

        Args:
            games_dict (Dict[str, Dict[str, Any]]):
                A dictionary keyed by game ID. Each value includes at least
                'description' and 'history' sub-dictionaries.

        Returns:
            pd.DataFrame: A DataFrame with one row per game, containing
            static and round-level information.
        """
        game_data_list = self.aggregate_game_data(games_dict)
        return pd.DataFrame([gd.to_dict() for gd in game_data_list])

    def _process_single_game(
        self, game_id: str, game_details: Dict[str, Any]
    ) -> Optional[GameData]:
        """
        Orchestrates the creation of a GameData object for one game.

        Args:
            game_id (str): Unique identifier for the game.
            game_details (Dict[str, Any]): Dictionary containing 'description' and 'history'.

        Returns:
            GameData|None: A GameData object if sufficient data is present,
            otherwise None if critical information is missing.
        """
        description = game_details.get("description", {})
        if not description:
            logger.warning("Game %s has no description; skipping.", game_id)
            return None

        language, n_rounds, n_rounds_is_known, agents_communicate = \
            self._parse_game_description(description)
        agents_info_list = self._extract_agents_info(description)
        if not agents_info_list:
            logger.warning("Game %s has no agent information; skipping.", game_id)
            return None

        history = game_details.get("history", {})
        agents_round_data = self._build_agents_round_data(
            agents_info_list, history, agents_communicate
        )

        return GameData(
            game_id=game_id,
            language=language,
            n_rounds=n_rounds,
            n_rounds_is_known=n_rounds_is_known,
            agents_communicate=agents_communicate,
            agents=agents_info_list,
            agents_round_data=agents_round_data
        )

    def _parse_game_description(
        self, description: Dict[str, Any]
    ) -> Tuple[Optional[str], Optional[int], bool, bool]:
        """
        Extracts core fields from the game description.

        Args:
            description (Dict[str, Any]): Contains descriptive fields of the game,
                                          such as language, n_rounds, etc.

        Returns:
            Tuple[Optional[str], Optional[int], bool, bool]:
            A tuple of (language, n_rounds, n_rounds_is_known, agents_communicate).
        """
        language = description.get("language")
        n_rounds = description.get("n_rounds")
        n_rounds_is_known = description.get("number_of_rounds_is_known", False)
        agents_communicate = description.get("agents_communicate", False)
        return language, n_rounds, n_rounds_is_known, agents_communicate

    def _build_agents_round_data(
        self,
        agents_info_list: List[AgentInfo],
        history: Dict[str, Any],
        agents_communicate: bool
    ) -> Dict[str, Dict[str, List[Any]]]:
        """
        Creates a dictionary mapping agent names to their round-level data.

        Args:
            agents_info_list (List[AgentInfo]): List of AgentInfo objects for the current game.
            history (Dict[str, Any]): Dictionary keyed by round identifiers,
                                      each containing a list of actions.
            agents_communicate (bool): Whether agents exchange messages.

        Returns:
            Dict[str, Dict[str, List[Any]]]: A dictionary whose keys are agent names
            and values are dictionaries of round data (strategies, scores, messages).
        """
        agents_round_data = {}
        for agent in agents_info_list:
            agent_name = agent.name
            agents_round_data[agent_name] = self._extract_agent_round_data(
                history, agent_name, agents_communicate
            )
        return agents_round_data

    def _extract_agents_info(self, description: Dict[str, Any]) -> List[AgentInfo]:
        """
        Creates AgentInfo objects from the 'agents' data in the description.

        Args:
            description (Dict[str, Any]): A dictionary containing 'agents' sub-dict.

        Returns:
            List[AgentInfo]: A list of AgentInfo objects, or an empty list if none found.
        """
        agents_data = description.get("agents", {})
        if not agents_data:
            return []

        agent_info_list = []
        for agent_data in agents_data.values():
            name = agent_data.get("name")
            llm_service = agent_data.get("llm_service", "")
            personality = agent_data.get("personality", "")
            opponent_prob = agent_data.get("opponent_personality_probability", 0.0)

            if not name:
                logger.warning("Agent entry missing a 'name'; skipping this agent.")
                continue

            agent_info_list.append(
                AgentInfo(
                    name=name,
                    llm_service=llm_service,
                    personality=personality,
                    opponent_prob=opponent_prob
                )
            )
        return agent_info_list

    def _extract_agent_round_data(
        self,
        history: Dict[str, Any],
        agent_name: str,
        agents_communicate: bool
    ) -> Dict[str, List[Any]]:
        """
        Extracts round-level data for a single agent.

        Args:
            history (Dict[str, Any]): Dictionary keyed by round identifier, each
                                      containing a list of action dictionaries.
            agent_name (str): Name of the agent whose actions we want to capture.
            agents_communicate (bool): Whether to capture messages from the agent's actions.

        Returns:
            Dict[str, List[Any]]: A dictionary with 'strategies', 'scores', and (optionally) 'messages'.
        """
        strategies, scores, messages = [], [], []

        for round_actions in history.values():
            for action in round_actions:
                if action.get("agent") == agent_name:
                    strategies.append(action.get("strategy"))
                    scores.append(action.get("score"))
                    if agents_communicate:
                        messages.append(action.get("message"))

        return {
            "strategies": strategies,
            "scores": scores,
            "messages": messages
        }
