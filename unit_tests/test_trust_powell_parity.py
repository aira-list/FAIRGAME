"""Parity with FAIRGAME-Trust (Powell et al.) on the v2 architecture.

Every assertion in the fork's ``unit_tests/test_game_round_trust.py`` has a
counterpart here. The fork's file cannot run verbatim: it imports
``src.fairgame_factory`` / ``src.game_round`` and drives a ``trust_settings``
dict, none of which survived the v2 rewrite. The *behaviour* it pins down is
what this file holds v2 to, expressed through v2's APIs.

Two deliberate differences from the fork, both inherited from v2 and not from
Powell:

* scores are payoffs to **maximise** (v2 does ``score -= look_cost``); the
  fork minimises a penalty (``score += look_cost``). Magnitudes match, signs
  do not.
* ``trust_cost`` is a float; the fork asserted ``isinstance(..., int)``, which
  its own shipped config (``lookCost: 0.25``) would have failed.

The scope tests at the bottom cover the fork's richer history model, which v2
v1 reduced to ``historyScope: "full"``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.communication.trust import LOOK, NO_LOOK, TrustConfig
from src.factory.fairgame_factory import FairGameFactory
from src.game.game_history import GameHistory
from src.game.game_round import GameRound
from src.io_managers.io_manager import IoManager
from src.results_processing.results_processor import ResultsProcessor

BASE_DIR = Path(__file__).resolve().parent

POWELL_CONFIG = "prisoner_dilemma_trust_powell.json"


def _factory() -> FairGameFactory:
    factory = FairGameFactory()
    factory.set_io_manager(IoManager(root_path=str(BASE_DIR)))
    return factory


def _run(config_name: str = POWELL_CONFIG):
    return _factory().load_config_create_and_run_games(config_name)


class _StubAgent:
    def __init__(self, name: str) -> None:
        self.name = name


class _StubGame:
    """Minimal stand-in for the fork's FakeGame, on v2's collaborator contract."""

    fake_communication_config = None

    def __init__(self, current_round: int = 1, **trust_kwargs) -> None:
        self.current_round = current_round
        self.trust_config = TrustConfig(enabled=True, look_cost=1.0, **trust_kwargs)
        self.history = GameHistory()


# ---- Powell 1: the config surface --------------------------------------


def test_trust_config_exposes_every_field_the_fork_configured():
    """The fork's trust block drove five settings; v2 v1 kept only three."""
    cfg = TrustConfig.from_config(
        {
            "trust": {
                "enabled": True,
                "actions": ["LOOK", "NO_LOOK"],
                "lookCost": 1,
                "historyScope": "full",
                "historyRounds": 1,
            }
        }
    )
    assert cfg.enabled is True
    assert cfg.actions == ["LOOK", "NO_LOOK"]
    assert cfg.look_cost == 1
    assert cfg.history_scope == "full"
    assert cfg.history_rounds == 1


def test_factory_builds_game_with_powell_trust_settings():
    factory = _factory()
    factory.create_games(factory.load_config(POWELL_CONFIG))
    assert len(factory.games) > 0
    cfg = factory.games[0].trust_config
    assert cfg.enabled is True
    assert cfg.actions == ["LOOK", "NO_LOOK"]
    assert cfg.look_cost == 1
    assert cfg.history_scope == "full"
    assert cfg.history_rounds == 1


# ---- Powell 4: parsing the monitoring decision -------------------------


@pytest.mark.parametrize(
    ("reply", "expected"),
    [("LOOK", LOOK), ("NO_LOOK", NO_LOOK), ("something else", NO_LOOK), ("", NO_LOOK)],
)
def test_parse_trust_action_defaults_to_no_look(reply, expected):
    assert TrustConfig.parse_action(reply) == expected


# ---- Powell 2 & 3: the phase records decisions, and only when enabled ---


def test_trust_phase_records_decision_per_agent():
    results = _run()
    history = results["game_0"]["history"]
    for round_entries in history.values():
        for entry in round_entries:
            assert entry["trust_action"] in (LOOK, NO_LOOK)


def test_trust_disabled_records_no_trust_fields():
    """v2 rows carry every schema key, so "not recorded" reads as ``None``
    where the fork asserted the key was absent from its sparse dicts."""
    results = _factory().load_config_create_and_run_games("prisoner_dilemma_mixed.json")
    history = results["game_0"]["history"]
    for round_entries in history.values():
        for entry in round_entries:
            assert entry.get("trust_action") is None

    df = ResultsProcessor().process(results)
    assert "agent1_trust_actions" not in df.columns
    assert "agent1_look_ratio" not in df.columns


# ---- Powell 5: a "none" personality never reaches the prompt -----------


def test_trust_prompt_hides_none_personality():
    factory = _factory()
    factory.create_games(factory.load_config(POWELL_CONFIG))
    game = factory.games[0]
    runner = GameRound(game)
    agent = next(iter(game.agents.values()))
    prompt = runner.create_prompt(agent, phase="trust")
    assert "You are none." not in prompt
    assert LOOK in prompt and NO_LOOK in prompt


# ---- Powell 6: end-to-end, five rounds, trust fields on every entry ----


def test_full_game_runs_five_rounds_and_records_trust_fields():
    results = _run()
    game = results["game_0"]
    history = game["history"]
    assert len(history) == 5

    for round_entries in history.values():
        assert len(round_entries) == 2  # two agents
        for entry in round_entries:
            assert entry["trust_action"] in (LOOK, NO_LOOK)
            assert isinstance(entry["trust_cost"], float)
            assert entry["strategy"] is not None
            assert entry["score"] is not None


# ---- Powell 7: the processed DataFrame carries the fork's columns ------


@pytest.mark.parametrize("agent", ["agent1", "agent2"])
@pytest.mark.parametrize(
    "column",
    [
        "trust_actions",
        "trust_costs",
        "total_trust_cost",
        "look_count",
        "no_look_count",
        "look_ratio",
    ],
)
def test_processed_dataframe_has_fork_trust_columns(agent, column):
    df = ResultsProcessor().process(_run())
    assert f"{agent}_{column}" in df.columns


def test_processed_dataframe_trust_values_are_well_formed():
    df = ResultsProcessor().process(_run())
    assert len(df) > 0
    row = df.iloc[0]

    for agent in ("agent1", "agent2"):
        assert len(row[f"{agent}_trust_actions"]) == 5
        assert len(row[f"{agent}_trust_costs"]) == 5

        actions = [a for a in row[f"{agent}_trust_actions"] if a is not None]
        assert len(actions) > 0
        assert all(a in (LOOK, NO_LOOK) for a in actions)

        assert row[f"{agent}_total_trust_cost"] >= 0
        assert row[f"{agent}_look_count"] >= 0
        assert row[f"{agent}_no_look_count"] >= 0
        assert 0 <= row[f"{agent}_look_ratio"] <= 1
        assert row[f"{agent}_look_count"] + row[f"{agent}_no_look_count"] == len(actions)


def test_look_count_and_ratio_agree_with_the_actions_list():
    df = ResultsProcessor().process(_run())
    row = df.iloc[0]
    actions = [a for a in row["agent1_trust_actions"] if a is not None]
    looks = sum(1 for a in actions if a == LOOK)
    assert row["agent1_look_count"] == looks
    assert row["agent1_look_ratio"] == pytest.approx(looks / len(actions))
    assert row["agent1_total_trust_cost"] == pytest.approx(looks * 1.0)


# ---- The fork's history model, which v2 v1 dropped ---------------------


def _seed_rounds(game: _StubGame, upto: int, trust_action: str | None = None) -> None:
    """Fill rounds 1..upto with a play by each agent (optionally a decision)."""
    for r in range(1, upto + 1):
        for name in ("agent1", "agent2"):
            entry = {"strategy": "Cooperate", "score": 3.0, "message": f"hi {r}"}
            if trust_action is not None and name == "agent1":
                entry["trust_action"] = trust_action
            game.history.update_round(r, name, entry)


def test_history_scope_last_x_shows_only_the_most_recent_rounds():
    game = _StubGame(current_round=5, history_scope="last_x", history_rounds=2)
    _seed_rounds(game, 4)
    runner = GameRound(game)
    runner.trust_decisions["agent1"] = LOOK

    visible = runner._visible_history(_StubAgent("agent1"), "choose")

    assert sorted(visible) == ["round_3", "round_4"]


def test_look_unlocks_the_previous_round_for_later_rounds():
    """The fork's retention rule: LOOK in round t unlocks t-1 permanently."""
    game = _StubGame(current_round=4, history_scope="only_paid_to_look_last_1")
    _seed_rounds(game, 3)
    # The agent paid to look in round 2, which unlocked round 1.
    game.history.update_round(2, "agent1", {"trust_action": LOOK})
    runner = GameRound(game)

    # In the trust prompt the agent sees what it already unlocked - and only that.
    visible = runner._visible_history(_StubAgent("agent1"), "trust")

    assert "round_1" in visible
    assert "round_3" not in visible


def test_only_paid_to_look_last_1_adds_the_current_previous_round():
    game = _StubGame(current_round=4, history_scope="only_paid_to_look_last_1")
    _seed_rounds(game, 3)
    game.history.update_round(2, "agent1", {"trust_action": LOOK})
    runner = GameRound(game)
    runner.trust_decisions["agent1"] = LOOK

    visible = runner._visible_history(_StubAgent("agent1"), "choose")

    # Retained round 1, plus round 3 (t-1) bought by this round's LOOK.
    assert "round_1" in visible
    assert "round_3" in visible
    assert "round_2" not in visible


def test_no_look_still_shows_nothing_under_every_scope():
    game = _StubGame(current_round=4, history_scope="only_paid_to_look_last_1")
    _seed_rounds(game, 3)
    game.history.update_round(2, "agent1", {"trust_action": LOOK})
    runner = GameRound(game)
    runner.trust_decisions["agent1"] = NO_LOOK

    assert runner._visible_history(_StubAgent("agent1"), "choose") == {}


def test_history_fields_limits_what_a_paid_look_reveals():
    game = _StubGame(current_round=3, history_fields=["strategy", "score"])
    _seed_rounds(game, 2)
    runner = GameRound(game)
    runner.trust_decisions["agent1"] = LOOK

    visible = runner._visible_history(_StubAgent("agent1"), "choose")

    for round_entries in visible.values():
        for entry in round_entries.values():
            assert set(entry) <= {"strategy", "score"}
            assert "message" not in entry


def test_unknown_history_scope_is_rejected():
    with pytest.raises(ValueError, match="historyScope"):
        TrustConfig(enabled=True, look_cost=1.0, history_scope="nonsense")
