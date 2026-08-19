"""End-to-end tests for the trust / costly-monitoring mechanism."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.communication.trust import TrustConfig
from src.factory.fairgame_factory import FairGameFactory
from src.game.phases import ChoosePhase, TrustPhase, phases_for_game
from src.io_managers.io_manager import IoManager
from src.results_processing.results_processor import ResultsProcessor

BASE_DIR = Path(__file__).resolve().parent


def _factory() -> FairGameFactory:
    factory = FairGameFactory()
    factory.set_io_manager(IoManager(root_path=str(BASE_DIR)))
    return factory


def _run(config_name: str):
    return _factory().load_config_create_and_run_games(config_name)


# ---- Phase wiring -------------------------------------------------------


class _StubGame:
    """Mirrors the GameConfig-backed contract: collaborator configs are
    always present (disabled by default), never None/missing."""

    def __init__(self, trust_enabled):
        from src.communication.fake_message_generator import FakeCommunicationConfig

        self.agents_communicate = False
        self.fake_communication_config = FakeCommunicationConfig(enabled=False)
        self.elicit_beliefs = False
        self.tom_order = 1
        self.trust_config = TrustConfig(enabled=trust_enabled, look_cost=1.0)


def test_trust_phase_inserted_before_choose_when_enabled():
    phases = phases_for_game(_StubGame(trust_enabled=True))
    assert any(isinstance(p, TrustPhase) for p in phases)
    trust_idx = next(i for i, p in enumerate(phases) if isinstance(p, TrustPhase))
    choose_idx = next(i for i, p in enumerate(phases) if isinstance(p, ChoosePhase))
    assert trust_idx < choose_idx


def test_no_trust_phase_when_disabled():
    phases = phases_for_game(_StubGame(trust_enabled=False))
    assert not any(isinstance(p, TrustPhase) for p in phases)


# ---- LLM agents that LOOK (fake connector elects LOOK) ------------------


def test_look_path_records_action_and_charges_cost():
    results = _run("prisoner_dilemma_trust.json")
    history = results["game_0"]["history"]
    for round_entries in history.values():
        for entry in round_entries:
            assert entry["trust_action"] == "LOOK"
            assert entry["trust_cost"] == 1
            # Both fake agents cooperate -> gross payoff 3, minus look cost 1.
            assert entry["score"] == pytest.approx(2.0)


def test_look_metrics_in_dataframe():
    results = _run("prisoner_dilemma_trust.json")
    df = ResultsProcessor().process(results)
    row = df.iloc[0]
    assert row["agent1_look_rate"] == pytest.approx(1.0)
    assert row["agent2_look_rate"] == pytest.approx(1.0)
    # 3 rounds * cost 1.
    assert row["agent1_monitoring_cost_total"] == pytest.approx(3.0)
    assert row["agent1_trust_actions"] == ["LOOK", "LOOK", "LOOK"]


# ---- Baseline agents always NO_LOOK -------------------------------------


def test_baselines_never_look_and_pay_nothing():
    results = _run("prisoner_dilemma_trust_baseline.json")
    history = results["game_0"]["history"]
    for round_entries in history.values():
        for entry in round_entries:
            assert entry["trust_action"] == "NO_LOOK"
            assert entry["trust_cost"] == 0.0
    df = ResultsProcessor().process(results)
    row = df.iloc[0]
    assert row["agent1_look_rate"] == pytest.approx(0.0)
    assert row["agent1_monitoring_cost_total"] == pytest.approx(0.0)
    # AlwaysCooperate vs AlwaysDefect, no monitoring cost: 0 and 5 each round.
    assert row["agent1_scores"] == [0.0, 0.0, 0.0]
    assert row["agent2_scores"] == [5.0, 5.0, 5.0]


# ---- Disabled trust leaves results clean --------------------------------


def test_disabled_trust_has_no_trust_columns():
    results = _run("prisoner_dilemma_mixed.json")  # an existing non-trust config
    df = ResultsProcessor().process(results)
    assert "agent1_look_rate" not in df.columns
    assert "agent1_trust_actions" not in df.columns


# ---- History gating (the core mechanic) ---------------------------------


def test_visible_history_gating():
    from src.communication.trust import TrustConfig
    from src.game.game_history import GameHistory
    from src.game.game_round import GameRound

    class _Game:
        current_round = 2
        fake_communication_config = None

        def __init__(self):
            self.trust_config = TrustConfig(enabled=True, look_cost=1.0)
            self.history = GameHistory()
            self.history.update_round(1, "agent1", {"strategy": "Cooperate", "score": 3})

    class _Agent:
        name = "agent1"

    game = _Game()
    runner = GameRound(game)
    agent = _Agent()

    # The trust prompt never shows history (you haven't looked yet).
    assert runner._visible_history(agent, "trust") == {}
    # Undecided / NO_LOOK -> no opponent history in the choose prompt.
    assert runner._visible_history(agent, "choose") == {}
    # LOOK -> full history revealed.
    runner.trust_decisions["agent1"] = "LOOK"
    assert runner._visible_history(agent, "choose") != {}
    # Trust disabled -> always full history (unchanged behaviour).
    game.trust_config = TrustConfig(enabled=False)
    assert runner._visible_history(agent, "choose") != {}


def test_trust_block_survives_validation():
    from src.io_managers.configuration_validator import ConfigValidator

    factory = _factory()
    raw = factory.load_config("prisoner_dilemma_trust.json")
    validated = ConfigValidator().validate_config_structure(raw)
    assert validated.get("trust", {}).get("enabled") is True
    assert validated["trust"]["lookCost"] == 1
