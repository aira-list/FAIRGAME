"""Tests for the per-round phase hierarchy.

GameRound's run() now delegates to a list of Phase objects:

* CommunicationPhase — runs first when ``agents_communicate`` is True
  (or fake-communication is enabled).
* BeliefPhase — runs second when ``elicit_beliefs`` is True.
* ChoosePhase — always runs last; produces the round's strategy keys.

Each phase is a focused unit; this file tests them in isolation.
"""

from __future__ import annotations

import unittest
from unittest import mock

from src.phases import (
    BeliefPhase,
    ChoosePhase,
    CommunicationPhase,
    Phase,
    phases_for_game,
)


class _FakeFairGame:
    """Minimal FairGame stand-in for phase isolation tests.

    Mirrors the GameConfig-backed contract: the collaborator configs are
    always present (disabled by default), never None/missing.
    """

    def __init__(self, **kwargs) -> None:
        from src.fake_message_generator import FakeCommunicationConfig
        from src.trust import TrustConfig

        self.agents_communicate = kwargs.get("agents_communicate", False)
        self.elicit_beliefs = kwargs.get("elicit_beliefs", False)
        self.tom_order = kwargs.get("tom_order", 1)
        self.fake_communication_config = kwargs.get(
            "fake_communication_config", FakeCommunicationConfig(enabled=False)
        )
        self.trust_config = kwargs.get("trust_config", TrustConfig(enabled=False))
        self.mixed_strategies = kwargs.get("mixed_strategies", False)


# ---------------------------------------------------------------------------
# phases_for_game ordering / inclusion
# ---------------------------------------------------------------------------


class TestPhaseSelection(unittest.TestCase):
    def test_choose_phase_is_always_last(self) -> None:
        game = _FakeFairGame()
        phases = phases_for_game(game)
        self.assertIsInstance(phases[-1], ChoosePhase)

    def test_no_communication_no_belief_means_choose_only(self) -> None:
        phases = phases_for_game(_FakeFairGame())
        self.assertEqual(len(phases), 1)
        self.assertIsInstance(phases[0], ChoosePhase)

    def test_communication_phase_added_when_enabled(self) -> None:
        phases = phases_for_game(_FakeFairGame(agents_communicate=True))
        types = [type(p) for p in phases]
        self.assertEqual(types, [CommunicationPhase, ChoosePhase])

    def test_belief_phase_added_when_enabled(self) -> None:
        phases = phases_for_game(_FakeFairGame(elicit_beliefs=True))
        types = [type(p) for p in phases]
        self.assertEqual(types, [BeliefPhase, ChoosePhase])

    def test_communication_runs_before_belief(self) -> None:
        phases = phases_for_game(_FakeFairGame(agents_communicate=True, elicit_beliefs=True))
        types = [type(p) for p in phases]
        self.assertEqual(types, [CommunicationPhase, BeliefPhase, ChoosePhase])

    def test_phase_objects_implement_protocol(self) -> None:
        phases = phases_for_game(_FakeFairGame(agents_communicate=True, elicit_beliefs=True))
        for phase in phases:
            self.assertIsInstance(phase, Phase)


# ---------------------------------------------------------------------------
# Phase.run delegates to the right collaborator on GameRound
# ---------------------------------------------------------------------------


class TestPhaseRunDelegation(unittest.TestCase):
    """Each phase must call exactly one method on the round runner — no
    cross-talk between phases."""

    def test_communication_phase_calls_execute_communication_phase(self) -> None:
        round_runner = mock.Mock()
        CommunicationPhase().run(round_runner)
        round_runner.execute_communication_phase.assert_called_once_with()
        round_runner.execute_belief_phase.assert_not_called()

    def test_belief_phase_calls_execute_belief_phase(self) -> None:
        round_runner = mock.Mock()
        BeliefPhase().run(round_runner)
        round_runner.execute_belief_phase.assert_called_once_with()
        round_runner.execute_communication_phase.assert_not_called()

    def test_choose_phase_returns_round_strategies(self) -> None:
        round_runner = mock.Mock()
        round_runner.execute_choose_phase.return_value = ["strategy1", "strategy2"]
        result = ChoosePhase().run(round_runner)
        self.assertEqual(result, ["strategy1", "strategy2"])
        round_runner.execute_choose_phase.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
