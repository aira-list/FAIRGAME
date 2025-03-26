
class GameHistory:
    """
    Manages round-by-round history data.
    The round data structure is maintained as a dictionary.
    """

    def __init__(self):
        """
        Initialize the GameHistory with an empty rounds dictionary.
        """
        self.rounds = {}

    def update_round(self, round_number, agent_name, data):
        """
        Update the record for a specific round and agent with new data.

        Args:
            round_number (int): The round index to update.
            agent_name (str): The identifier of the agent.
            data (dict): The data to store for this agent in this round.
        """
        round_key = f'round_{round_number}'
        if round_key not in self.rounds:
            self.rounds[round_key] = {}
        self.rounds[round_key].setdefault(agent_name, {}).update(data)

    def get_round_data(self, round_number):
        """
        Retrieve data for a specific round.

        Args:
            round_number (int): The round index.

        Returns:
            dict: A dictionary of agent data for the specified round.
        """
        return self.rounds.get(f'round_{round_number}', {})

    def get_last_round_choices(self):
        """
        Retrieve the strategies chosen by each agent in the last recorded round.

        Returns:
            dict or None: A dict mapping agent names to their 'strategy' choice in
                          the last round, or None if no rounds have been recorded.
        """
        if not self.rounds:
            return None
        last_round_key = max(self.rounds.keys(), key=lambda k: int(k.split('_')[1]))
        return {agent: outcome.get('strategy')
                for agent, outcome in self.rounds[last_round_key].items()}

    @property
    def all_rounds(self):
        """
        dict: All round data stored so far.
        """
        return self.rounds
    
    def __str__(self):
        """
        String representation of the entire history dictionary.
        """
        return str(self.rounds)

    def describe(self):
        """
        Returns a dict where keys are round strings like 'round_1', 'round_2', etc.
        Each value is a list of agent data dictionaries.

        Returns:
            dict: A round-keyed dictionary describing the game history.
        """
        summary = {}
        
        # Sort round keys by the numeric part to ensure correct ordering
        sorted_round_keys = sorted(self.rounds.keys(),
                                   key=lambda k: int(k.split('_')[1]))
        
        for round_key in sorted_round_keys:
            agents_data = self.rounds[round_key]
            round_list = []
            
            for agent_name, data in agents_data.items():
                round_list.append({
                    "agent": agent_name,
                    "message": data.get("message"),
                    "message_prompt": data.get("message_prompt"),
                    "choice_prompt": data.get("choice_prompt"),
                    "strategy": data.get("strategy"),
                    "score": data.get("score"),
                })
            
            summary[round_key] = round_list
        
        return summary