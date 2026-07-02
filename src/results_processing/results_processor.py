import logging
from typing import Any

import pandas as pd

from src.game_config import DescKey
from src.results_processing.agent_info import AgentInfo
from src.results_processing.game_data import GameData

logger = logging.getLogger(__name__)


class ResultsProcessor:
    """
    Processes game results and converts them into structured GameData objects and pandas DataFrames.
    """

    def aggregate_game_data(self, games_dict: dict[str, dict[str, Any]]) -> list[GameData]:
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

    def process(self, games_dict: dict[str, dict[str, Any]]) -> pd.DataFrame:
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

    def _process_single_game(self, game_id: str, game_details: dict[str, Any]) -> GameData | None:
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

        language, n_rounds, n_rounds_is_known, agents_communicate = self._parse_game_description(
            description
        )
        agents_info_list = self._extract_agents_info(description)
        if not agents_info_list:
            logger.warning("Game %s has no agent information; skipping.", game_id)
            return None

        # Fake/covert channels also record messages in history even though
        # the config's agents_communicate flag stays off — keep them in the
        # output rather than silently dropping the channel under study.
        record_messages = agents_communicate or bool(
            description.get(DescKey.FAKE_COMMUNICATION, False)
        )
        history = game_details.get("history", {})
        agents_round_data = self._build_agents_round_data(
            agents_info_list, history, record_messages
        )

        return GameData(
            game_id=game_id,
            language=language,
            n_rounds=n_rounds,
            n_rounds_is_known=n_rounds_is_known,
            agents_communicate=agents_communicate,
            agents=agents_info_list,
            agents_round_data=agents_round_data,
            elicit_beliefs=bool(description.get(DescKey.ELICIT_BELIEFS, False)),
            tom_order=int(description.get(DescKey.TOM_ORDER, 1)),
            equilibria=list(description.get(DescKey.EQUILIBRIA, []) or []),
            payoff_matrix_summary=description.get(DescKey.PAYOFF_MATRIX_SUMMARY),
            language_for_matrix=language,
            pareto_optimal_sum=description.get(DescKey.PARETO_OPTIMAL_SUM),
            seed=description.get(DescKey.SEED),
            payoff_variant_name=description.get(DescKey.PAYOFF_VARIANT_NAME),
            record_messages=record_messages,
        )

    def _parse_game_description(
        self, description: dict[str, Any]
    ) -> tuple[str | None, int | None, bool, bool]:
        """
        Extracts core fields from the game description.

        Args:
            description (Dict[str, Any]): Contains descriptive fields of the game,
                                          such as language, n_rounds, etc.

        Returns:
            Tuple[Optional[str], Optional[int], bool, bool]:
            A tuple of (language, n_rounds, n_rounds_is_known, agents_communicate).
        """
        language = description.get(DescKey.LANGUAGE)
        n_rounds = description.get(DescKey.N_ROUNDS)
        n_rounds_is_known = description.get(DescKey.N_ROUNDS_IS_KNOWN, False)
        agents_communicate = description.get(DescKey.AGENTS_COMMUNICATE, False)
        return language, n_rounds, n_rounds_is_known, agents_communicate

    def _build_agents_round_data(
        self, agents_info_list: list[AgentInfo], history: dict[str, Any], record_messages: bool
    ) -> dict[str, dict[str, list[Any]]]:
        """
        Creates a dictionary mapping agent names to their round-level data.

        Args:
            agents_info_list (List[AgentInfo]): List of AgentInfo objects for the current game.
            history (Dict[str, Any]): Dictionary keyed by round identifiers,
                                      each containing a list of actions.
            record_messages (bool): Whether the game recorded messages
                (real communication or a fake/covert channel).

        Returns:
            Dict[str, Dict[str, List[Any]]]: A dictionary whose keys are agent names
            and values are dictionaries of round data (strategies, scores, messages).
        """
        agents_round_data = {}
        for agent in agents_info_list:
            agent_name = agent.name
            agents_round_data[agent_name] = self._extract_agent_round_data(
                history, agent_name, record_messages
            )
        return agents_round_data

    def _extract_agents_info(self, description: dict[str, Any]) -> list[AgentInfo]:
        """
        Creates AgentInfo objects from the 'agents' data in the description.

        Args:
            description (Dict[str, Any]): A dictionary containing 'agents' sub-dict.

        Returns:
            List[AgentInfo]: A list of AgentInfo objects, or an empty list if none found.
        """
        agents_data = description.get(DescKey.AGENTS, {})
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
                    opponent_prob=opponent_prob,
                    agent_type=agent_data.get("agent_type"),
                    baseline_strategy=agent_data.get("baseline_strategy"),
                )
            )
        return agent_info_list

    def _extract_agent_round_data(
        self, history: dict[str, Any], agent_name: str, record_messages: bool
    ) -> dict[str, list[Any]]:
        """
        Extracts round-level data for a single agent.

        Captures strategies, scores, optional messages, and (when ToM belief
        elicitation is enabled) the per-round belief distributions.
        """
        strategies, scores, messages = [], [], []
        beliefs, beliefs_2nd_order = [], []
        trust_actions, trust_costs = [], []

        for round_actions in history.values():
            for action in round_actions:
                if action.get("agent") == agent_name:
                    strategies.append(action.get("strategy"))
                    scores.append(action.get("score"))
                    if record_messages:
                        messages.append(action.get("message"))
                    beliefs.append(action.get("belief"))
                    beliefs_2nd_order.append(action.get("belief_2nd_order"))
                    trust_actions.append(action.get("trust_action"))
                    trust_costs.append(action.get("trust_cost"))

        return {
            "strategies": strategies,
            "scores": scores,
            "messages": messages,
            "beliefs": beliefs,
            "beliefs_2nd_order": beliefs_2nd_order,
            "trust_actions": trust_actions,
            "trust_costs": trust_costs,
        }
