from typing import Any, Dict, List
from src.llm_connectors.llm_factory_connector import execute_prompt


class Agent:
    """
    Represents an agent that interacts with a language model service to decide on strategies.
    
    The Agent stores its own history of strategies and scores, and it can execute a round
    by sending a prompt to the LLM service.
    """

    def __init__(self, name: str, llm_service: str, personality: str, opponent_personality_prob: int) -> None:
        """
        Initialize the Agent instance.

        Args:
            name (str): The name of the agent.
            llm_service (str): Identifier or configuration for the LLM service used to execute prompts.
            personality (str): The personality descriptor for the agent.
            opponent_personality_prob (int): The probability (as an integer percentage) that the opponent
                                             will behave cooperatively.
        """
        self.name: str = name
        self.strategies: List[str] = []
        self.scores: List[int] = []
        self.llm_service: str = llm_service
        self.personality: str = personality
        self.opponent_personality_prob: int = opponent_personality_prob

    def execute_round(self, prompt: str) -> str:
        """
        Execute a round by sending a prompt to the LLM service and returning the agent's choice.

        Args:
            prompt (str): The prompt to send to the language model.

        Returns:
            str: The choice or response returned by the language model.
        """
        choice = execute_prompt(self.llm_service, prompt)
        return choice

    def add_strategy(self, strategy: str) -> None:
        """
        Record a new strategy choice.

        Args:
            strategy (str): The strategy chosen by the agent.
        """
        self.strategies.append(strategy)

    def last_strategy(self) -> str:
        """
        Retrieve the most recent strategy choice.

        Returns:
            str: The last strategy from the agent's history.
        """
        return self.strategies[-1]

    def add_score(self, score: int) -> None:
        """
        Record a new score for the agent.

        Args:
            score (int): The score to be added.
        """
        self.scores.append(score)

    def last_score(self) -> int:
        """
        Retrieve the most recent score.

        Returns:
            int: The last score recorded.
        """
        return self.scores[-1]

    def get_info(self) -> Dict[str, Any]:
        """
        Retrieve all pertinent information about the agent.

        Returns:
            dict: A dictionary containing the agent's name, LLM service, personality, and
                  opponent personality probability.
        """
        return {
            "name": self.name,
            "llm_service": self.llm_service,
            "personality": self.personality,
            "opponent_personality_probability": self.opponent_personality_prob
        }
