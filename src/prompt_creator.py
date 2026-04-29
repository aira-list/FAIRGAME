"""Fill prompt templates with per-round, per-agent, ToM-aware values."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)

PHASE_BLOCKS = ("communicate", "choose", "believe", "mixedChoose")


class PromptCreator:
    """Render the per-round prompt for a single agent.

    Supported template block markers (each of the form ``{name}:[...]``):

    * ``intro`` — agent identity / personality block.
    * ``opponentIntro`` — block that mentions the opponent. Stripped when
      ``tom_order == 0``.
    * ``gameLength`` — round-count block, kept only when ``nRoundsIsKnown``.
    * ``communicate``, ``choose``, ``believe`` — phase blocks; only the
      block matching the active phase is retained.
    * ``secondOrder`` — second-order ToM block; kept only when
      ``tom_order >= 2``.
    * ``ownType`` — block referring to the agent's private type; stripped
      if no type is configured.
    """

    def __init__(
        self,
        lang: str,
        prompt_template: str,
        n_rounds: int,
        n_rounds_known: bool,
        payoff_matrix,
        *,
        tom_order: int = 1,
    ) -> None:
        self.language = lang
        self.prompt_template = prompt_template
        self.n_rounds = n_rounds
        self.n_rounds_known = n_rounds_known
        self.payoff_matrix = payoff_matrix
        self.tom_order = tom_order

    # ---- Block helpers --------------------------------------------------

    def _find_part(self, field_name):
        pattern = rf"\{{{field_name}\}}:\s*\[(.*?)\]"
        return re.search(pattern, self.prompt_template, flags=re.DOTALL)

    def _remove_part(self, part):
        if part:
            self.prompt_template = self.prompt_template.replace(part.group(0), "")

    def _replace_part(self, part, replacement=None):
        if not part:
            return
        if replacement is not None:
            self.prompt_template = self.prompt_template.replace(part.group(0), replacement)
        else:
            self.prompt_template = self.prompt_template.replace(part.group(0), part.group(1))

    # ---- Block processors -----------------------------------------------

    def process_intro(self, agent, pv_dict: Dict[str, Any]) -> None:
        intro = self._find_part("intro")
        if intro is None:
            return
        if agent.personality == "None":
            self._remove_part(intro)
        else:
            self._replace_part(intro)
            pv_dict["personality"] = agent.personality

    def process_opponent_intro(self, agent, opponents, pv_dict: Dict[str, Any]) -> None:
        opponent_intro = self._find_part("opponentIntro")
        if opponent_intro is None:
            return

        # ToM order 0 explicitly suppresses opponent information.
        if self.tom_order < 1:
            self._remove_part(opponent_intro)
            return

        valid_opponents_exist = any(
            (opp.opponent_personality_prob != 0 and opp.personality != "None")
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

    def process_game_length(self, pv_dict: Dict[str, Any]) -> None:
        game_length = self._find_part("gameLength")
        if game_length is None:
            return
        if self.n_rounds_known:
            self._replace_part(game_length)
            pv_dict["nRounds"] = self.n_rounds
        else:
            self._remove_part(game_length)

    def process_second_order(self) -> None:
        block = self._find_part("secondOrder")
        if block is None:
            return
        if self.tom_order >= 2:
            self._replace_part(block)
        else:
            self._remove_part(block)

    def process_own_type(self, pv_dict: Dict[str, Any]) -> None:
        block = self._find_part("ownType")
        if block is None:
            return
        if "ownType" in pv_dict:
            self._replace_part(block)
        else:
            self._remove_part(block)

    # ---- Placeholder map ------------------------------------------------

    def map_placeholders(
        self,
        agent_name: str,
        opponents,
        current_round: int,
        history: Dict,
    ) -> Dict[str, Any]:
        strategies_keys = list(self.payoff_matrix.strategies.keys())
        weight_keys = list(self.payoff_matrix.weights.keys())

        values: Dict[str, Any] = {
            "currentPlayerName": agent_name,
            "currentRound": current_round,
            "history": history,
        }
        for i, key in enumerate(strategies_keys):
            values[f"strategy{i+1}"] = self.payoff_matrix.strategies[key]
        for i, key in enumerate(weight_keys):
            values[f"weight{i+1}"] = self.payoff_matrix.weights[key]
        for i, opp in enumerate(opponents, start=1):
            values[f"opponent{i}"] = opp.name
        return values

    # ---- Phase routing --------------------------------------------------

    def _apply_phase(self, phase: str) -> None:
        """Keep only the block matching ``phase`` and drop the others.

        If ``phase == "choose"`` and a ``{mixedChoose}`` block is present it
        is *not* removed automatically; the caller decides which one wins by
        passing either ``"choose"`` or ``"mixedChoose"`` as the phase.
        """
        for name in PHASE_BLOCKS:
            block = self._find_part(name)
            if block is None:
                continue
            if name == phase:
                self._replace_part(block)
            else:
                self._remove_part(block)

    def process_optional_parts(self, agent, opponents, pv_dict: Dict[str, Any]) -> None:
        self.process_intro(agent, pv_dict)
        self.process_opponent_intro(agent, opponents, pv_dict)
        self.process_game_length(pv_dict)
        self.process_second_order()
        self.process_own_type(pv_dict)

    # ---- Main entry -----------------------------------------------------

    def fill_template(
        self,
        agent,
        opponents,
        current_round: int,
        history: Dict,
        phase: str,
        *,
        extra_placeholders: Optional[Dict[str, Any]] = None,
    ) -> str:
        placeholder_value_dict = self.map_placeholders(
            agent.name, opponents, current_round, history
        )
        if extra_placeholders:
            placeholder_value_dict.update(extra_placeholders)

        self.process_optional_parts(agent, opponents, placeholder_value_dict)
        self._apply_phase(phase)

        logger.debug("Filled prompt template:\n%s", self.prompt_template)
        return self.prompt_template.format(**placeholder_value_dict)
