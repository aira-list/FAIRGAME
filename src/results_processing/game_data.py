from typing import Dict, Any, List, Optional

from src.results_processing.agent_info import AgentInfo

class GameData:
    """
    Encapsulates all relevant data for a single game, including static and round-level data.
    """

    def __init__(
        self,
        game_id: str,
        language: Optional[str],
        n_rounds: Optional[int],
        n_rounds_is_known: bool,
        agents_communicate: bool,
        agents: List[AgentInfo],
        agents_round_data: Dict[str, Dict[str, List[Any]]]
    ):
        """
        Initializes a GameData instance.

        Args:
            game_id (str): Unique identifier for the game.
            language (str|None): The language in which the game is played (e.g., "English").
            n_rounds (int|None): The maximum number of rounds (if known).
            n_rounds_is_known (bool): Whether the number of rounds is known to the agents.
            agents_communicate (bool): Whether agents can exchange messages.
            agents (List[AgentInfo]): List of AgentInfo objects describing each agent.
            agents_round_data (Dict[str, Dict[str, List[Any]]]):
                A mapping of each agent's name to another dictionary with
                'strategies', 'scores', and 'messages' (if communication is enabled).
        """
        self.game_id = game_id
        self.language = language
        self.n_rounds = n_rounds
        self.n_rounds_is_known = n_rounds_is_known
        self.agents_communicate = agents_communicate
        self.agents = agents
        self.agents_round_data = agents_round_data

    def to_dict(self) -> Dict[str, Any]:
        """
        Returns a dictionary representation of this game's data, suitable for DataFrame rows.

        Returns:
            Dict[str, Any]: A dictionary containing all necessary fields to represent this game.
        """
        row = {
            "game_id": self.game_id,
            "language": self.language,
            "n_rounds_is_known": self.n_rounds_is_known,
            "max_rounds": self.n_rounds,
            "played_rounds": max(
                len(agent_data["strategies"]) for agent_data in self.agents_round_data.values()
            ) if self.agents_round_data else 0,
            "agents_communicate": self.agents_communicate,
        }

        # Populate each agent's static and round-level data
        for idx, agent in enumerate(self.agents, start=1):
            prefix = f"agent{idx}_"
            row.update(agent.to_dict(prefix=prefix))

            agent_name = agent.name
            round_data = self.agents_round_data.get(agent_name, {
                "strategies": [],
                "scores": [],
                "messages": []
            })
            row[f"{prefix}strategies"] = round_data["strategies"]
            row[f"{prefix}scores"] = round_data["scores"]
            row[f"{prefix}messages"] = (
                round_data["messages"] if self.agents_communicate else []
            )

        return row

