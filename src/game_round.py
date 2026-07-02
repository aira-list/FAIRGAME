"""Single-round execution: communication phase + belief elicitation + strategy selection."""

from __future__ import annotations

import os
import re
from typing import Any

from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_fixed,
)

from src.belief_parser import BeliefParseError, parse_belief
from src.fake_message_generator import FakeMessageGenerator
from src.prompt_creator import PromptCreator
from src.utils.logger import get_logger

# parse_belief is imported above; alias kept for clarity in mixed-strategy code.

logger = get_logger(__name__)


def _extract_numeric_message(prompt: str, raw: str, message_format: str | None = None) -> str:
    """Extract the covert numeric sequence from a communicate-phase response.

    Some models (e.g. Haiku) ignore "output only numbers" and prepend reasoning
    prose, which would corrupt the symbol/entropy analysis and change what the
    opponent sees. When the channel is numeric, pull out the longest
    comma-separated number run; natural-language messages pass through
    untouched, as do responses with no detectable numeric run.

    The channel shape comes from ``message_format`` when the config declares
    it (``"dec"`` / ``"hex"`` / ``"text"`` — language-independent and the
    preferred path). ``None`` falls back to sniffing the rendered prompt for
    the English covert-template phrases ("exactly 10", "hexadecimal") — kept
    only for configs written before ``messageFormat`` existed; it cannot work
    for non-English templates.
    """
    if message_format == "text":
        return raw
    if message_format in ("dec", "hex"):
        hex_mode = message_format == "hex"
    else:
        p = prompt.lower()
        if "exactly 10" not in p and "10 numbers" not in p and "10 hexadecimal" not in p:
            return raw  # NL channel or non-numeric: leave message as-is
        hex_mode = "hexadecimal" in p
    token = r"[0-9a-fA-F]{1,3}" if hex_mode else r"[0-9]{1,3}"
    # a run of >=4 comma-separated tokens (covert messages are 10) — avoids
    # catching incidental "1, 2" mentions in prose.
    pattern = re.compile(rf"{token}(?:\s*,\s*{token}){{3,}}")
    matches = pattern.findall(raw)
    if not matches:
        return raw.strip()  # fallback: don't destroy an unparseable message
    best = max(matches, key=lambda m: m.count(","))  # the 10-number sequence
    return ",".join(t.strip() for t in best.split(","))


def _strategy_max_attempts() -> int:
    raw = os.getenv("FAIRGAME_STRATEGY_MAX_ATTEMPTS", "10")
    try:
        return max(1, int(raw))
    except ValueError:
        return 10


def _belief_max_attempts() -> int:
    raw = os.getenv("FAIRGAME_BELIEF_MAX_ATTEMPTS", "3")
    try:
        return max(1, int(raw))
    except ValueError:
        return 3


class GameRound:
    """Encapsulates one round of a FAIRGAME match."""

    def __init__(self, game) -> None:
        self.game = game
        self.round_number = game.current_round
        # Per-agent monitoring decision for this round (LOOK / NO_LOOK).
        # Populated by the trust phase; empty when trust is disabled.
        self.trust_decisions: dict[str, str] = {}

        self.fake_generator = None
        fake_cfg = getattr(game, "fake_communication_config", None)
        if fake_cfg and getattr(fake_cfg, "enabled", False):
            self.fake_generator = FakeMessageGenerator(
                count=fake_cfg.message_count,
                base=fake_cfg.base,
                rng=getattr(game, "rng", None),
            )

    def run(self) -> list[str]:
        """Execute one full round and return the strategy keys chosen.

        Delegates to a list of :class:`Phase` objects, in fixed order:
        communication (if enabled) → belief elicitation (if enabled) →
        choose (always). Only the choose phase produces a value the
        engine cares about; the others are pure side-effects on history.
        """
        from src.phases import ChoosePhase  # local: avoid cycles

        result: list[str] = []
        # Frozen, resolved-once phase list owned by the game.
        for phase in self.game.phases:
            output = phase.run(self)
            if isinstance(phase, ChoosePhase):
                result = output  # type: ignore[assignment]
        return result

    # Entry point for ChoosePhase (see src.phases): collects one strategy
    # per agent and returns the round's strategy keys in agent order.
    def execute_choose_phase(self) -> list[str]:
        choose_phase = "mixedChoose" if self.game.mixed_strategies else "choose"
        round_strategies: list[str] = []
        for agent in self.game.agents.values():
            prompt = self.create_prompt(agent, phase=choose_phase)
            strategy = self._execute_agent_strategy(agent, prompt)
            round_strategies.append(strategy)

        return round_strategies

    # ---- Communication --------------------------------------------------

    def execute_communication_phase(self) -> None:
        for agent in self.game.agents.values():
            if self.fake_generator:
                message = self.fake_generator.generate(agent, self.round_number)
            else:
                message = self._get_real_message(agent)

            self.game.history.update_round(
                self.round_number,
                agent.name,
                {"message": message},
            )

    def _get_real_message(self, agent) -> str:
        prompt = self.create_prompt(agent, phase="communicate")
        raw = agent.execute_round(prompt)
        return _extract_numeric_message(
            prompt, raw, message_format=getattr(self.game, "message_format", None)
        )

    # ---- Trust / costly monitoring --------------------------------------

    def execute_trust_phase(self) -> None:
        """Ask each agent whether to LOOK (pay to see history) or NO_LOOK.

        Baseline agents never read prompts, so they deterministically
        ``NO_LOOK`` (act on trust, incur no cost). LLM agents are prompted
        with the ``{trust}`` block and their reply is parsed; anything
        ambiguous falls back to ``NO_LOOK``.
        """
        from src.agent import BaselineAgent  # local import to avoid cycle
        from src.trust import NO_LOOK, TrustConfig

        for agent in self.game.agents.values():
            if isinstance(agent, BaselineAgent):
                action = NO_LOOK
            else:
                prompt = self.create_prompt(agent, phase="trust")
                raw = agent.execute_round(prompt)
                action = TrustConfig.parse_action(raw)
            # Record only the decision here; the per-round history write
            # (trust_action + trust_cost, the single source of truth) happens
            # in record_round_history once the score is finalised.
            self.trust_decisions[agent.name] = action

    # Same-round state that is private to the agent who produced it: another
    # agent's just-elicited belief or mixed-strategy distribution must never
    # appear in a prompt before that round's choices are made — it would
    # disclose a prediction/intent the game hasn't revealed yet. (Messages
    # are deliberately shared: that's what the communication phase is for.)
    _SAME_ROUND_PRIVATE_FIELDS = ("belief", "belief_2nd_order", "mixed_distribution")

    def _visible_history(self, agent, phase: str) -> dict:
        """History the agent may use when building the prompt for ``phase``.

        Three independent gates apply, in order:

        1. **Same-round privacy** — other agents' in-progress round entries
           are stripped of private fields (see
           :attr:`_SAME_ROUND_PRIVATE_FIELDS`).
        2. **Trust** — with the costly-monitoring mechanism on, the trust
           prompt itself shows nothing (the agent hasn't looked yet) and the
           later phases show history only if the agent paid to ``LOOK``.
        3. **Interaction graph** — the surviving history is then filtered to
           what this agent is allowed to perceive: a source's plays only if
           the agent can *see* it, and a source's message only if the agent
           can *hear* it (see :class:`src.interaction.InteractionGraph`).

        With trust disabled and no (or a complete) graph this is the full
        prompt-safe view — unchanged legacy behaviour.
        """
        base = self.game.history.prompt_view()
        current_key = f"round_{self.round_number}"
        if base.get(current_key):
            # Rebuild (never mutate) the view: prompt_view may share dicts
            # with the underlying history.
            base = dict(base)
            base[current_key] = {
                source: (
                    data  # an agent may see its own same-round state
                    if source == agent.name
                    else {k: v for k, v in data.items() if k not in self._SAME_ROUND_PRIVATE_FIELDS}
                )
                for source, data in base[current_key].items()
            }
        trust_cfg = getattr(self.game, "trust_config", None)
        if trust_cfg and getattr(trust_cfg, "enabled", False):
            from src.trust import LOOK

            if phase == "trust" or self.trust_decisions.get(agent.name) != LOOK:
                base = {}
        return self._apply_interaction_filter(agent, base)

    def _apply_interaction_filter(self, agent, view: dict) -> dict:
        """Trim ``view`` to what ``agent`` may perceive under the graph.

        Field-level: a source the agent can *see* contributes its plays
        (everything except ``message``); a source the agent can *hear* also
        contributes its ``message``; a source the agent can neither see nor
        hear is dropped. The agent's own row is always kept in full.
        """
        graph = getattr(self.game, "interaction_graph", None)
        if graph is None or graph.is_fully_connected or not view:
            return view
        filtered: dict[str, dict] = {}
        for round_key, agents_data in view.items():
            kept: dict[str, dict] = {}
            for source, data in agents_data.items():
                if source == agent.name:
                    kept[source] = data
                    continue
                sees = graph.sees(agent.name, source)
                hears = graph.hears(agent.name, source)
                if not sees and not hears:
                    continue
                entry = {k: v for k, v in data.items() if k != "message"} if sees else {}
                if hears and "message" in data:
                    entry["message"] = data["message"]
                kept[source] = entry
            filtered[round_key] = kept
        return filtered

    # ---- Belief elicitation --------------------------------------------

    def execute_belief_phase(self) -> None:
        """Ask each agent to predict its opponents' next strategy.

        Failures are recorded but do not abort the round — research code
        often wants to see *that* an agent failed to articulate a belief.
        """
        for agent in self.game.agents.values():
            prompt = self.create_prompt(agent, phase="believe")
            belief = self._elicit_one_belief(agent, prompt)
            self.game.history.update_round(
                self.round_number,
                agent.name,
                {"belief": belief, "belief_prompt": prompt},
            )

    def execute_belief_second_order_phase(self) -> None:
        """Ask each agent to predict its opponent's belief about it.

        The result is a probability distribution over the agent's *own*
        strategy keys: "what does the opponent think *I* will do?".
        Used together with the opponent's first-order belief from the
        same round to compute second-order Brier scores.

        If the template doesn't carry a ``{believe2}: […]`` block we
        silently skip — there's nothing to send and forcing a prompt
        would just trigger retry storms when the LLM has no instructions.
        Same retry/parse path as the first-order belief phase otherwise.
        """
        if "{believe2}:" not in (self.game.prompt_template or ""):
            logger.debug(
                "Skipping second-order belief phase: template has no {believe2}: [...] block."
            )
            return
        for agent in self.game.agents.values():
            prompt = self.create_prompt(agent, phase="believe2")
            belief = self._elicit_one_belief(agent, prompt)
            self.game.history.update_round(
                self.round_number,
                agent.name,
                {"belief_2nd_order": belief, "belief_2nd_order_prompt": prompt},
            )

    @staticmethod
    def _retrying(max_attempts: int, exc_types) -> Retrying:
        """Shared retry policy for LLM elicitation loops: fixed 1s backoff,
        retry only on parse/matching failures, re-raise after the last try."""
        return Retrying(
            stop=stop_after_attempt(max_attempts),
            wait=wait_fixed(1),
            retry=retry_if_exception_type(exc_types),
            reraise=True,
        )

    def _elicit_one_belief(self, agent, prompt: str) -> dict[str, float] | None:
        retrying = self._retrying(_belief_max_attempts(), BeliefParseError)
        try:
            for attempt in retrying:
                with attempt:
                    response = agent.execute_round(prompt)
                    logger.debug("Agent %s belief raw response: %s", agent.name, response)
                    return parse_belief(response, self.game.payoff_matrix.strategies)
        except BeliefParseError as exc:
            logger.warning(
                "Could not parse belief for agent %s after %d attempts: %s",
                agent.name,
                _belief_max_attempts(),
                exc,
            )
            return None
        return None  # pragma: no cover - tenacity always returns or raises

    # ---- Choose ---------------------------------------------------------

    def create_prompt(self, agent, phase: str) -> str:
        opponents = self._get_opponents(agent)
        # Behavioural framing: describe the discount / risk preference to the
        # agent when its mode is "prompt" or "both". Risk framing only applies
        # to CRRA (prompt-side fairness isn't supported yet).
        discount_mode = getattr(self.game, "discount_mode", "score")
        risk_mode = getattr(self.game, "risk_mode", "score")
        transform_name = getattr(getattr(self.game, "utility_transform", None), "name", "identity")
        prompt_creator = PromptCreator(
            self.game.language,
            self.game.prompt_template,
            self.game.n_rounds,
            self.game.n_rounds_known,
            self.game.payoff_matrix,
            tom_order=getattr(self.game, "tom_order", 1),
            reputation_window=getattr(self.game, "reputation_window", None),
            reputation_applies=getattr(self.game, "reputation_applies", True),
            discount_in_prompt=discount_mode in ("prompt", "both"),
            discount_factor=getattr(self.game, "discount_factor", 1.0),
            risk_in_prompt=risk_mode in ("prompt", "both") and transform_name == "crra",
        )
        return prompt_creator.fill_template(
            agent,
            opponents,
            self.round_number,
            # Prompt-safe view: excludes the bulky ``*_prompt`` audit fields so
            # the history fed via ``{history}`` never re-embeds prior prompts
            # (which caused exponential history growth / OOM in ToM games).
            # When the trust mechanism is on, this view is gated by the
            # agent's monitoring decision (NO_LOOK → no opponent history).
            self._visible_history(agent, phase),
            phase,
            extra_placeholders=self._tom_placeholders(agent, opponents),
        )

    def _tom_placeholders(self, agent, opponents) -> dict[str, Any]:
        """Build ToM-aware placeholders (own type, opponent type prior, ...)."""
        values: dict[str, Any] = {}
        own_type = getattr(agent, "agent_type", None)
        if own_type is not None:
            values["ownType"] = own_type

        types_cfg = getattr(self.game, "types_config", None)
        if types_cfg and getattr(self.game, "types_common_knowledge", False):
            labels = list(types_cfg.get("labels", []))
            probs = types_cfg.get("probs") or [1 / len(labels)] * len(labels)
            values["typeDistribution"] = ", ".join(
                f"{lab}={p:.2f}" for lab, p in zip(labels, probs, strict=False)
            )
        return values

    def _get_opponents(self, agent):
        """Opponents to surface in ``agent``'s prompt.

        Defaults to every other agent (the implicit clique). When a reduced
        interaction graph is configured, opponents the agent cannot see are
        omitted from the prompt — the agent still *plays* them (payoffs are
        unchanged), it just isn't told about them.
        """
        others = [a for a in self.game.agents.values() if a != agent]
        graph = getattr(self.game, "interaction_graph", None)
        if graph is None or graph.is_fully_connected:
            return others
        return [a for a in others if graph.sees(agent.name, a.name)]

    def _execute_agent_strategy(self, agent, prompt: str) -> str:
        # Polymorphic dispatch: BaselineAgent picks via its strategy
        # object, LLMAgent goes through the LLM call.
        from src.agent import BaselineAgent  # local import to avoid cycle

        if isinstance(agent, BaselineAgent):
            strategy_key = agent.baseline_strategy.choose(agent, self.game, self.round_number)
            agent.add_strategy(self.game.payoff_matrix.strategies[strategy_key])
            return strategy_key

        if self.game.mixed_strategies:
            return self._execute_mixed_strategy(agent, prompt)

        retrying = self._retrying(_strategy_max_attempts(), ValueError)
        for attempt in retrying:
            with attempt:
                response = agent.execute_round(prompt)
                logger.debug("Agent %s raw response: %s", agent.name, response)
                strategy_key = self._match_strategy(response)
                if strategy_key is None:
                    raise ValueError(f"No matching strategy in response from agent {agent.name!r}.")
                agent.add_strategy(self.game.payoff_matrix.strategies[strategy_key])
                return strategy_key
        raise RuntimeError("Strategy retry loop exited unexpectedly")  # pragma: no cover

    def _execute_mixed_strategy(self, agent, prompt: str) -> str:
        """Ask the agent for a distribution and sample one strategy from it."""
        retrying = self._retrying(_strategy_max_attempts(), (ValueError, BeliefParseError))
        for attempt in retrying:
            with attempt:
                response = agent.execute_round(prompt)
                logger.debug("Agent %s mixed response: %s", agent.name, response)
                distribution = parse_belief(response, self.game.payoff_matrix.strategies)
                # Record the elicited distribution as well as the sampled action.
                self.game.history.update_round(
                    self.round_number,
                    agent.name,
                    {"mixed_distribution": distribution},
                )
                keys = list(distribution.keys())
                weights = list(distribution.values())
                strategy_key = self.game.rng.choices(keys, weights=weights, k=1)[0]
                agent.add_strategy(self.game.payoff_matrix.strategies[strategy_key])
                return strategy_key
        raise RuntimeError("Mixed-strategy retry loop exited unexpectedly")  # pragma: no cover

    def _match_strategy(self, response: str) -> str | None:
        """Resolve an LLM response to a strategy key.

        Preference order: (1) the response *is* a label (the prompt asks for
        "ONLY the choice"); (2) exactly one label appears somewhere in the
        text; (3) several labels appear — take the one mentioned last, which
        matches the "reasoning first, final answer last" shape of ambiguous
        replies ("Rather than Cooperate, I Defect"). Dict order no longer
        decides ties: when two labels start at the same position (one is a
        substring of the other, e.g. "Cooperate" vs "Cooperate more"), the
        longer, more specific label wins.
        """
        normalised = response.lower().strip().strip(".\"'`")
        for key, label in self.game.payoff_matrix.strategies.items():
            if normalised == label.lower():
                return key
        best_key: str | None = None
        best_rank = (-1, -1)  # (last start position, label length) — higher wins
        for key, label in self.game.payoff_matrix.strategies.items():
            lowered = label.lower()
            pos = normalised.rfind(lowered)
            if pos < 0:
                continue
            rank = (pos, len(lowered))
            if rank > best_rank:
                best_rank = rank
                best_key = key
        return best_key

    def record_round_history(self) -> None:
        trust_cfg = getattr(self.game, "trust_config", None)
        trust_on = bool(trust_cfg and getattr(trust_cfg, "enabled", False))
        look_cost = float(getattr(trust_cfg, "look_cost", 0.0) or 0.0) if trust_on else 0.0
        from src.trust import LOOK

        for agent in self.game.agents.values():
            data = {
                "strategy": agent.last_strategy(),
                "score": agent.last_score(),
            }
            if trust_on:
                action = self.trust_decisions.get(agent.name, "NO_LOOK")
                data["trust_action"] = action
                data["trust_cost"] = look_cost if action == LOOK else 0.0
            self.game.history.update_round(self.round_number, agent.name, data)
