
from src.prompt_creator import PromptCreator
from retry import retry

class GameRound:
    """
    Represents a single round in the game, handling both communication
    and strategy selection phases for all agents.
    """

    def __init__(self, game):
        """
        Initialize with a reference to the FairGame instance.

        Args:
            game (FairGame): The main game object containing all configuration,
                             agents, history, and the payoff matrix.
        """
        self.game = game
        self.round_number = game.current_round

    def run(self):
        """
        Execute one round of the game.

        If agents_communicate is True, they each receive a communication prompt
        and respond with a message. Afterwards, they receive a strategy prompt
        and choose a strategy.

        Returns:
            list of str: The list of strategy keys (not names) chosen by agents this round.
        """
        if self.game.agents_communicate:
            self._execute_communication_phase()

        round_strategies = []
        for agent in self.game.agents.values():
            prompt = self.create_prompt(agent, phase='choose')
            strategy = self._execute_agent_strategy(agent, prompt)
            round_strategies.append(strategy)

        return round_strategies

    def _execute_communication_phase(self):
        """
        Sends a communication prompt to each agent and records the resulting message
        in the game history.
        """
        for agent in self.game.agents.values():
            prompt = self.create_prompt(agent, phase='communicate')
            message = agent.execute_round(prompt)
            self.game.history.update_round(self.round_number, agent.name, {
                'message_prompt': prompt,
                'message': message
            })

    def create_prompt(self, agent, phase):
        """
        Create a prompt for an agent based on the current game state.

        Args:
            agent: The agent object to create the prompt for.
            phase (str): The phase of the round ('communicate' or 'choose').

        Returns:
            str: The prompt to be sent to the agent.
        """
        opponents = self._get_opponents(agent)
        prompt_creator = PromptCreator(
            self.game.language,
            self.game.prompt_template,
            self.game.n_rounds,
            self.game.n_rounds_known,
            self.game.payoff_matrix
        )
        return prompt_creator.fill_template(
            agent,
            opponents,
            self.round_number,
            self.game.history.rounds,
            phase
        )

    def _get_opponents(self, agent):
        """
        Retrieve all other agents in the game that are not the specified agent.

        Args:
            agent: The reference agent.

        Returns:
            list: A list of all agent objects except the reference agent.
        """
        return [a for a in self.game.agents.values() if a != agent]

    @retry(tries=10, delay=1)
    def _execute_agent_strategy(self, agent, prompt):
        """
        Retrieve a strategy from the agent after giving it a strategy prompt.

        Uses retry to handle cases where the agent fails to provide a valid strategy.

        Args:
            agent: The agent object whose strategy is being determined.
            prompt (str): The strategy prompt.

        Returns:
            str: The strategy key selected by the agent.

        Raises:
            ValueError: If no matching strategy is found in the agent's response.
        """
        response = agent.execute_round(prompt)
        print("RESPONSE ", response)
        found_strategy = next(
            (key for key, val in self.game.payoff_matrix.strategies.items()
             if val.lower() in response.lower()),
            None
        )
        if found_strategy:
            agent.add_strategy(self.game.payoff_matrix.strategies[found_strategy])
            return found_strategy
        raise ValueError("No matching strategy found")

    def _update_round_history(self):
        """
        Update the game history with each agent's final strategy and score for this round.
        """
        for agent in self.game.agents.values():
            self.game.history.update_round(self.round_number, agent.name, {
                'strategy': agent.last_strategy(),
                'score': agent.last_score()
            })
