import re

class PromptCreator:
   
    def __init__(self, lang, prompt_template, n_rounds, n_rounds_known, payoff_matrix):
        self.language = lang
        self.prompt_template = prompt_template
        self.n_rounds = n_rounds
        self.n_rounds_known = n_rounds_known
        self.payoff_matrix = payoff_matrix

    def _find_part(self, field_name):
        """
        Finds a portion of the template of the form:
        {field_name}:[ ...some text... ]
        Returns the match object or None if not found.
        """
        pattern = rf"\{{{field_name}\}}:\s*\[(.*?)\]"
        match = re.search(pattern, self.prompt_template, flags=re.DOTALL)
        return match
    
    def _remove_part(self, part):
        """Removes the entire matched portion from the template."""
        if part:
            self.prompt_template = self.prompt_template.replace(part.group(0), '')

    def _replace_part(self, part, replacement=None):
        """
        Replaces the entire matched portion with its inside text (part.group(1)),
        or if 'replacement' is provided, uses that instead.
        """
        if part:
            if replacement is not None:
                self.prompt_template = self.prompt_template.replace(part.group(0), replacement)
            else:
                self.prompt_template = self.prompt_template.replace(part.group(0), part.group(1))

    def process_intro(self, agent, pv_dict):
        """
        If agent has no personality, remove the block. Otherwise replace it
        and add agent.personality to the placeholder-value dict.
        """
        intro = self._find_part('intro')
        if intro is None:
            return
        
        if agent.personality == 'None':
            self._remove_part(intro)
        else:
            self._replace_part(intro)
            pv_dict['personality'] = agent.personality

    def process_opponent_intro(self, agent, opponents, pv_dict):
        """
        A new version that can handle multiple opponents.
        - If *all* opponents have no personality or a 0 probability, remove the block.
        - Otherwise, keep it and fill placeholders like:
            {opponent1}, {opponent2}, 
            {opponentPersonality1}, {opponentPersonality2}, 
            {opponentPersonalityProbability1}, {opponentPersonalityProbability2}, ...
        """
        opponent_intro = self._find_part('opponentIntro')
        if opponent_intro is None:
            return

        # Check if at least one opponent has a non-zero probability and a non-'None' personality
        valid_opponents_exist = any(
            (opp.opponent_personality_prob != 0 and opp.personality != 'None')
            for opp in opponents
        )

        if not valid_opponents_exist:
            # If no valid opponents exist, remove the entire block
            self._remove_part(opponent_intro)
        else:
            # Replace the block with the text in brackets as-is
            # (We still rely on placeholders inside that bracketed text, e.g., {opponent1}, etc.)
            self._replace_part(opponent_intro)

            # Build placeholders in the pv_dict for each opponent
            for i, opp in enumerate(opponents, start=1):
                pv_dict[f"opponent{i}"] = opp.name
                pv_dict[f"opponentPersonality{i}"] = opp.personality
                pv_dict[f"opponentPersonalityProbability{i}"] = opp.opponent_personality_prob

    def process_game_length(self, pv_dict):
        """
        If the number of rounds is known, keep the block and inject {nRounds}.
        Otherwise remove it.
        """
        game_length = self._find_part('gameLength')
        if game_length is None:
            return
        
        if self.n_rounds_known:
            self._replace_part(game_length)
            pv_dict['nRounds'] = self.n_rounds
        else:
            self._remove_part(game_length)


    def map_placeholders(self, agent_name, opponents, current_round, history):
        """
        Dynamically build the dictionary of placeholders to be injected later.
        In addition to agent_name, current_round, etc., we also add each opponent.
        This code also handles the payoff matrix placeholders (strategies, weights).
        """
        strategies_keys = list(self.payoff_matrix.strategies.keys())
        weight_keys = list(self.payoff_matrix.weights.keys())

        # Start with basic placeholders
        values = {
            'currentPlayerName': agent_name,
            'currentRound': current_round,
            'history': history,
        }

        # Add strategies and weights as in your original code
        for i, key in enumerate(strategies_keys):
            values[f"strategy{i+1}"] = self.payoff_matrix.strategies[key]
        for i, key in enumerate(weight_keys):
            values[f"weight{i+1}"] = self.payoff_matrix.weights[key]

        # Create placeholders for opponents in a simpler form, e.g. "OpponentA, OpponentB, ..."
        # so you can handle something like "{opponent1}, {opponent2}" in the text.
        for i, opp in enumerate(opponents, start=1):
            values[f"opponent{i}"] = opp.name

        return values 
    
    def process_optional_parts(self, agent, opponents, pv_dict):
        """A helper method that calls the other optional-part processors."""
        self.process_intro(agent, pv_dict)
        self.process_opponent_intro(agent, opponents, pv_dict)
        self.process_game_length(pv_dict)
    
    def fill_template(self, agent, opponents, current_round, history, phase):
        """
        The main entry point.
        1) Build placeholders.
        2) Process optional parts (intro, opponentIntro, gameLength).
        3) Handle phase blocks for 'communicate' and 'choose'.
        4) Format and return the final prompt.
        """

        # 1) Build placeholders
        placeholder_value_dict = self.map_placeholders(agent.name, opponents, current_round, history)

        # 2) Process intros/game length blocks
        self.process_optional_parts(agent, opponents, placeholder_value_dict)

        # 3) Handle the 'communicate' and 'choose' placeholders
        communicate_match = self._find_part('communicate')
        choose_match = self._find_part('choose')  # Usually always present

        phase_actions = {
            'communicate': {'replace': communicate_match, 'remove': choose_match},
            'choose':        {'replace': choose_match,     'remove': communicate_match}
        }

        if phase in phase_actions:
            actions = phase_actions[phase]
            if actions['replace'] is not None:
                self._replace_part(actions['replace'])
            if actions['remove'] is not None:
                self._remove_part(actions['remove'])
        prompt = self.prompt_template.format(**placeholder_value_dict)
        print(f"CURRENT PROMPT {prompt}")
        return prompt
