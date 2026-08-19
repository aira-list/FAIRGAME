"""Fill prompt templates with per-round, per-agent, ToM-aware values."""

from __future__ import annotations

import re
from typing import Any

from src.utils.logger import get_logger
from src.utils.utils import round_index

logger = get_logger(__name__)

PHASE_BLOCKS = ("communicate", "trust", "choose", "believe", "believe2", "mixedChoose")


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
    * ``discount`` — describes the per-round discount to the agent; kept only
      when ``discount_in_prompt`` and δ < 1 (behavioural discount mode).
    * ``riskFrame`` — describes a risk preference (CRRA) to the agent; kept
      only when ``risk_in_prompt`` (behavioural risk mode).
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
        reputation_window: int | None = None,
        reputation_applies: bool = True,
        discount_in_prompt: bool = False,
        discount_factor: float = 1.0,
        risk_in_prompt: bool = False,
    ) -> None:
        self.language = lang
        # Immutable source. Block processing mutates a per-render working copy
        # (``self.prompt_template``), reset from this at the start of every
        # ``fill_template`` so renders carry no side effects across calls.
        self._template_source = prompt_template
        self.prompt_template = prompt_template
        self.n_rounds = n_rounds
        self.n_rounds_known = n_rounds_known
        self.payoff_matrix = payoff_matrix
        self.tom_order = tom_order
        # When set (>=1), per-opponent {coopRateN}/{reputationN} placeholders
        # average only the most recent N rounds; otherwise they use the full
        # history.
        self.reputation_window = reputation_window
        # When False, ``{coopRateN}``/``{reputationN}`` are filled with
        # ``n/a``/``unknown`` regardless of history. Set this to False for
        # asymmetric coordination games (Battle of the Sexes), zero-sum
        # games, and any scenario where strategy1 doesn't mean "cooperate".
        self.reputation_applies = reputation_applies
        # Behavioural (prompt-side) framing of game-theoretic preferences.
        # When on, an optional ``{discount}`` / ``{riskFrame}`` block is kept
        # so the preference is described to the agent and shapes its choices.
        # When off, the block is stripped (and the preference, if any, acts
        # only on the score — see ``FairGame._apply_score_modifiers``).
        self.discount_in_prompt = discount_in_prompt
        self.discount_factor = discount_factor
        self.risk_in_prompt = risk_in_prompt

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

    def process_intro(self, agent, pv_dict: dict[str, Any]) -> None:
        intro = self._find_part("intro")
        if intro is None:
            return
        if agent.personality == "None":
            self._remove_part(intro)
        else:
            self._replace_part(intro)
            pv_dict["personality"] = agent.personality

    def process_opponent_intro(self, agent, opponents, pv_dict: dict[str, Any]) -> None:
        opponent_intro = self._find_part("opponentIntro")
        if opponent_intro is None:
            return

        # ToM order 0 explicitly suppresses opponent information.
        if self.tom_order < 1:
            self._remove_part(opponent_intro)
            return

        valid_opponents_exist = any(
            (opp.opponent_personality_prob != 0 and opp.personality != "None") for opp in opponents
        )

        if not valid_opponents_exist:
            self._remove_part(opponent_intro)
        else:
            self._replace_part(opponent_intro)
            for i, opp in enumerate(opponents, start=1):
                pv_dict[f"opponent{i}"] = opp.name
                pv_dict[f"opponentPersonality{i}"] = opp.personality
                pv_dict[f"opponentPersonalityProbability{i}"] = opp.opponent_personality_prob

    def process_game_length(self, pv_dict: dict[str, Any]) -> None:
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

    def process_own_type(self, pv_dict: dict[str, Any]) -> None:
        block = self._find_part("ownType")
        if block is None:
            return
        if "ownType" in pv_dict:
            self._replace_part(block)
        else:
            self._remove_part(block)

    def process_discount(self, pv_dict: dict[str, Any]) -> None:
        """Keep the ``{discount}`` block only when the discount is being
        described to the agent (``discount_mode`` in {prompt, both}) and it
        actually discounts (δ < 1). Fills ``{discountFactor}`` for templates
        that want to state the magnitude."""
        block = self._find_part("discount")
        if block is None:
            return
        if self.discount_in_prompt and self.discount_factor < 1.0:
            pv_dict["discountFactor"] = self.discount_factor
            self._replace_part(block)
        else:
            self._remove_part(block)

    def process_risk_frame(self) -> None:
        """Keep the ``{riskFrame}`` block only when a risk preference is being
        described to the agent (``risk_mode`` in {prompt, both} with a CRRA
        transform)."""
        block = self._find_part("riskFrame")
        if block is None:
            return
        if self.risk_in_prompt:
            self._replace_part(block)
        else:
            self._remove_part(block)

    # ---- Placeholder map ------------------------------------------------

    def map_placeholders(
        self,
        agent_name: str,
        opponents,
        current_round: int,
        history: dict,
    ) -> dict[str, Any]:
        strategies_keys = list(self.payoff_matrix.strategies.keys())
        weight_keys = list(self.payoff_matrix.weights.keys())

        values: dict[str, Any] = {
            "currentPlayerName": agent_name,
            "currentRound": current_round,
            "history": history,
        }
        for i, key in enumerate(strategies_keys):
            values[f"strategy{i + 1}"] = self.payoff_matrix.strategies[key]

        # Per-opponent reputation: rolling cooperation rate over their
        # past plays. By convention strategy1 = "cooperate". When
        # ``reputation_applies`` is False (asymmetric / zero-sum games),
        # we deliberately emit ``n/a`` / ``unknown`` so the labels
        # don't mislead the LLM.
        cooperate_label = (
            self.payoff_matrix.strategies.get(strategies_keys[0]) if strategies_keys else None
        )
        for i, opp in enumerate(opponents, start=1):
            rate: float | None = None
            if self.reputation_applies:
                rate = self._opponent_cooperation_rate(opp, history, cooperate_label)
            if rate is not None:
                values[f"coopRate{i}"] = f"{rate:.2f}"
                values[f"reputation{i}"] = self._reputation_label(rate)
            else:
                values[f"coopRate{i}"] = "n/a"
                values[f"reputation{i}"] = "unknown"
        for i, key in enumerate(weight_keys):
            values[f"weight{i + 1}"] = self.payoff_matrix.weights[key]
        for i, opp in enumerate(opponents, start=1):
            values[f"opponent{i}"] = opp.name
        return values

    # ---- Reputation helpers ---------------------------------------------

    def _opponent_cooperation_rate(self, opponent, history: dict, cooperate_label):
        """Fraction of past rounds in which ``opponent`` played the cooperate label.

        ``history`` is keyed by ``round_N`` and each value is a dict of
        ``{agent_name: {strategy: ..., ...}}``. ``self.reputation_window``,
        when set, restricts the average to the most recent N rounds.
        """
        if not history or cooperate_label is None:
            return None
        try:
            sorted_keys = sorted(history.keys(), key=round_index)
        except (IndexError, ValueError):
            return None
        if self.reputation_window:
            sorted_keys = sorted_keys[-int(self.reputation_window) :]

        total = 0
        cooperated = 0
        for key in sorted_keys:
            entry = history[key].get(opponent.name) if isinstance(history[key], dict) else None
            if not entry:
                continue
            strat = entry.get("strategy")
            if strat is None:
                continue
            total += 1
            if strat == cooperate_label:
                cooperated += 1
        if total == 0:
            return None
        return cooperated / total

    @staticmethod
    def _reputation_label(rate: float) -> str:
        if rate >= 0.75:
            return "highly cooperative"
        if rate >= 0.5:
            return "moderately cooperative"
        if rate >= 0.25:
            return "occasionally cooperative"
        return "uncooperative"

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

    def process_optional_parts(self, agent, opponents, pv_dict: dict[str, Any]) -> None:
        self.process_intro(agent, pv_dict)
        self.process_opponent_intro(agent, opponents, pv_dict)
        self.process_game_length(pv_dict)
        self.process_second_order()
        self.process_own_type(pv_dict)
        self.process_discount(pv_dict)
        self.process_risk_frame()

    # ---- Main entry -----------------------------------------------------

    def fill_template(
        self,
        agent,
        opponents,
        current_round: int,
        history: dict,
        phase: str,
        *,
        extra_placeholders: dict[str, Any] | None = None,
    ) -> str:
        # Start each render from the pristine source so block stripping never
        # leaks into the next render of the same instance.
        self.prompt_template = self._template_source

        placeholder_value_dict = self.map_placeholders(
            agent.name, opponents, current_round, history
        )
        if extra_placeholders:
            placeholder_value_dict.update(extra_placeholders)

        self.process_optional_parts(agent, opponents, placeholder_value_dict)
        self._apply_phase(phase)

        logger.debug("Filled prompt template:\n%s", self.prompt_template)
        return self.prompt_template.format(**placeholder_value_dict)
