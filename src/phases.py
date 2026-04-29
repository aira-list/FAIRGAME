"""Per-round phase objects.

A round of FAIRGAME has up to three phases that run in a fixed order:

1. :class:`CommunicationPhase` — agents exchange messages (real or fake).
2. :class:`BeliefPhase` — agents are asked to predict the opponent.
3. :class:`ChoosePhase` — agents pick a strategy.

Each phase is a small object with a single ``run(round_runner)`` method.
The round runner exposes the phase-specific entry points
(``_execute_communication_phase`` etc.) so the phase doesn't need to
know about the matrix, agents, history, or RNG directly.

The :func:`phases_for_game` factory inspects a :class:`FairGame` instance
and returns the ordered list of phases that should fire for it.
"""

from __future__ import annotations

import abc
from typing import List


class Phase(abc.ABC):
    """A single phase of one round."""

    @abc.abstractmethod
    def run(self, round_runner) -> object:
        """Execute the phase. Returns whatever the phase produces (or None)."""


class CommunicationPhase(Phase):
    """Agents exchange messages before choosing strategies."""

    def run(self, round_runner) -> None:
        round_runner._execute_communication_phase()


class BeliefPhase(Phase):
    """Agents are prompted to predict the opponent's next strategy."""

    def run(self, round_runner) -> None:
        round_runner._execute_belief_phase()


class ChoosePhase(Phase):
    """Agents pick the strategy that determines this round's payoff."""

    def run(self, round_runner) -> List[str]:
        return round_runner._execute_choose_phase()


def phases_for_game(game) -> List[Phase]:
    """Return the ordered list of phases for ``game``.

    Communication runs first if either real or fake communication is on,
    belief elicitation runs second, and choose always runs last.
    """
    phases: List[Phase] = []
    fake_cfg = getattr(game, "fake_communication_config", None)
    fake_enabled = bool(fake_cfg and getattr(fake_cfg, "enabled", False))
    if game.agents_communicate or fake_enabled:
        phases.append(CommunicationPhase())
    if getattr(game, "elicit_beliefs", False):
        phases.append(BeliefPhase())
    phases.append(ChoosePhase())
    return phases
