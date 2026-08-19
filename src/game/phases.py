"""Per-round phase objects.

A round of FAIRGAME has up to three phases that run in a fixed order:

1. :class:`CommunicationPhase` — agents exchange messages (real or fake).
2. :class:`BeliefPhase` — agents are asked to predict the opponent.
3. :class:`ChoosePhase` — agents pick a strategy.

Each phase is a small object with a single ``run(round_runner)`` method.
The round runner exposes the phase-specific entry points
(``execute_communication_phase`` etc.) so the phase doesn't need to
know about the matrix, agents, history, or RNG directly.

The :func:`phases_for_game` factory inspects a :class:`FairGame` instance
and returns the ordered list of phases that should fire for it.
"""

from __future__ import annotations

import abc


class Phase(abc.ABC):
    """A single phase of one round."""

    @abc.abstractmethod
    def run(self, round_runner) -> object:
        """Execute the phase. Returns whatever the phase produces (or None)."""


class CommunicationPhase(Phase):
    """Agents exchange messages before choosing strategies."""

    def run(self, round_runner) -> None:
        round_runner.execute_communication_phase()


class TrustPhase(Phase):
    """Agents make a costly monitoring decision (LOOK / NO_LOOK).

    Runs after communication and before belief/choose, so the decision
    gates the opponent history visible in those later phases (see
    :meth:`GameRound._visible_history`).
    """

    def run(self, round_runner) -> None:
        round_runner.execute_trust_phase()


class BeliefPhase(Phase):
    """Agents are prompted to predict the opponent's next strategy
    (a first-order belief: a distribution over the opponent's
    strategy keys)."""

    def run(self, round_runner) -> None:
        round_runner.execute_belief_phase()


class BeliefSecondOrderPhase(Phase):
    """Agents are prompted to predict their opponent's belief about
    them (a second-order belief: a distribution over the agent's
    *own* strategy keys, capturing what the agent thinks the opponent
    thinks the agent will do).

    Wired in only when ``elicit_beliefs`` is on AND ``tom_order >= 2``.
    """

    def run(self, round_runner) -> None:
        round_runner.execute_belief_second_order_phase()


class ChoosePhase(Phase):
    """Agents pick the strategy that determines this round's payoff."""

    def run(self, round_runner) -> list[str]:
        return round_runner.execute_choose_phase()


def phases_for_game(game) -> list[Phase]:
    """Return the ordered list of phases for ``game``.

    Communication runs first if either real or fake communication is on,
    belief elicitation runs second, and choose always runs last.
    """
    phases: list[Phase] = []
    # The collaborator configs (fake_communication_config, trust_config) are
    # guaranteed present on every game — they live on GameConfig.
    if game.agents_communicate or game.fake_communication_config.enabled:
        phases.append(CommunicationPhase())
    if game.trust_config.enabled:
        phases.append(TrustPhase())
    if game.elicit_beliefs:
        phases.append(BeliefPhase())
        # Higher-order belief elicitation: only fired when the configuration
        # actively asks for second-order ToM reasoning.
        if int(game.tom_order) >= 2:
            phases.append(BeliefSecondOrderPhase())
    phases.append(ChoosePhase())
    return phases
