import re
import ast

class PromptCreator:
   
    def __init__(self, lang, prompt_template, n_rounds, n_rounds_known, payoff_matrix):
        self.language = lang
        self.prompt_template = prompt_template
        self.n_rounds = n_rounds
        self.n_rounds_known = n_rounds_known
        self.payoff_matrix = payoff_matrix

    def _find_part(self, field_name):
        pattern = rf"\{{{field_name}\}}:\s*\[(.*?)\]"
        return re.search(pattern, self.prompt_template, flags=re.DOTALL)
    
    def _remove_part(self, part):
        if part:
            self.prompt_template = self.prompt_template.replace(part.group(0), '')

    def _replace_part(self, part, replacement=None):
        if part:
            self.prompt_template = self.prompt_template.replace(
                part.group(0),
                replacement if replacement is not None else part.group(1)
            )

    def process_intro(self, agent, pv_dict):
        intro = self._find_part('intro')
        if intro is None:
            return
        if agent.personality == 'None':
            self._remove_part(intro)
        else:
            self._replace_part(intro)
            pv_dict['personality'] = agent.personality

    def process_opponent_intro(self, agent, opponents, pv_dict):
        opponent_intro = self._find_part('opponentIntro')
        if opponent_intro is None:
            return

        valid_opponents_exist = any(
            (opp.opponent_personality_prob != 0 and opp.personality != 'None')
            for opp in opponents
        )

        if not valid_opponents_exist:
            self._remove_part(opponent_intro)
        else:
            self._replace_part(opponent_intro)
            for i, opp in enumerate(opponents, start=1):
                pv_dict[f"opponent{i}"] = opp.name
                pv_dict[f"opponentPersonality{i}"] = opp.personality
                pv_dict[f"opponentPersonalityProbability{i}"] = opp.opponent_personality_prob

    def process_game_length(self, pv_dict):
        game_length = self._find_part('gameLength')
        if game_length is None:
            return
        if self.n_rounds_known:
            self._replace_part(game_length)
            pv_dict['nRounds'] = self.n_rounds
        else:
            self._remove_part(game_length)

    def map_placeholders(self, agent_name, opponents, current_round, history):
        # Clean up over-escaped sequences safely
        clean_history = self._unescape_once(history)

        strategies_keys = list(self.payoff_matrix.strategies.keys())
        weight_keys = list(self.payoff_matrix.weights.keys())

        values = {
            'currentPlayerName': agent_name,
            'currentRound': current_round,
            'history': clean_history,
        }

        for i, key in enumerate(strategies_keys):
            values[f"strategy{i+1}"] = self.payoff_matrix.strategies[key]
        for i, key in enumerate(weight_keys):
            values[f"weight{i+1}"] = self.payoff_matrix.weights[key]

        for i, opp in enumerate(opponents, start=1):
            values[f"opponent{i}"] = opp.name

        return values 
    
    def process_optional_parts(self, agent, opponents, pv_dict):
        self.process_intro(agent, pv_dict)
        self.process_opponent_intro(agent, opponents, pv_dict)
        self.process_game_length(pv_dict)
    
    def fill_template(self, agent, opponents, current_round, history, phase):
        placeholder_value_dict = self.map_placeholders(agent.name, opponents, current_round, history)
        self.process_optional_parts(agent, opponents, placeholder_value_dict)

        communicate_match = self._find_part('communicate')
        choose_match = self._find_part('choose')

        phase_actions = {
            'communicate': {'replace': communicate_match, 'remove': choose_match},
            'choose': {'replace': choose_match, 'remove': communicate_match}
        }

        if phase in phase_actions:
            actions = phase_actions[phase]
            if actions['replace']:
                self._replace_part(actions['replace'])
            if actions['remove']:
                self._remove_part(actions['remove'])

        prompt = self.prompt_template.format(**placeholder_value_dict)
        print(f"CURRENT PROMPT {prompt}")
        return prompt

    @staticmethod
    def append_to_history(history, speaker, message):
        """Safe way to append dialogue to history without over-escaping."""
        return f"{history}\n{speaker}: {message}"

    @staticmethod
    def _unescape_once(text):
        """Elegant and safe way to unescape strings only once using ast.literal_eval."""
        try:
            return ast.literal_eval(f"'''{text}'''")
        except Exception:
            return text  # Return original if parsing fails
