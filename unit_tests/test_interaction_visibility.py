"""Tests for how the interaction graph filters per-agent prompt history.

These exercise :meth:`GameRound._visible_history` (field-level filtering)
and :meth:`GameRound._get_opponents` (prompt opponent scoping). The graph
is purely informational, so we only assert on what each agent perceives,
never on payoffs.
"""

from __future__ import annotations

from types import SimpleNamespace

from src.game_history import GameHistory
from src.game_round import GameRound
from src.interaction import InteractionGraph
from src.trust import LOOK, NO_LOOK


def _round(strategy, score, message):
    return {"strategy": strategy, "score": score, "message": message, "belief": None}


def _rounds():
    return {
        "round_1": {
            "A": _round("strategy1", 3, "msg-A"),
            "B": _round("strategy2", 0, "msg-B"),
            "C": _round("strategy1", 3, "msg-C"),
        }
    }


def _history(rounds=None):
    """A real GameHistory seeded from a ``{round_key: {agent: data}}`` map.

    Using the production object (not a stub) keeps ``prompt_view`` semantics —
    fresh dict per call, prompt-only fields excluded — faithful to runtime, so
    a change to that method can't pass here while breaking in production.
    """
    hist = GameHistory()
    for round_key, agents_data in (rounds or _rounds()).items():
        n = int(round_key.split("_")[1])
        for agent_name, data in agents_data.items():
            hist.update_round(n, agent_name, data)
    return hist


def _make_round(graph, *, trust_config=None, trust_decisions=None):
    game = SimpleNamespace(
        current_round=1,
        fake_communication_config=None,
        trust_config=trust_config,
        interaction_graph=graph,
        history=_history(),
    )
    gr = GameRound(game)
    if trust_decisions:
        gr.trust_decisions = dict(trust_decisions)
    return gr


def _agent(name):
    return SimpleNamespace(name=name)


def _expected_view_for(viewer):
    """The full history minus other agents' same-round private fields.

    ``current_round`` is 1 in these fixtures, so round_1 is the in-progress
    round: the viewer keeps its own entry in full, while other agents'
    ``belief``/``mixed_distribution`` are stripped (same-round privacy).
    """
    rounds = _rounds()
    for name, data in rounds["round_1"].items():
        if name != viewer:
            data.pop("belief", None)
    return rounds


# ---- Backward compatibility ---------------------------------------------


def test_no_graph_returns_full_history():
    gr = _make_round(graph=None)
    view = gr._visible_history(_agent("A"), "choose")
    assert view == _expected_view_for("A")


def test_complete_graph_returns_full_history():
    gr = _make_round(graph=InteractionGraph.complete(["A", "B", "C"]))
    view = gr._visible_history(_agent("A"), "choose")
    assert view == _expected_view_for("A")


def test_same_round_privacy_keeps_past_round_beliefs():
    # A completed round's beliefs stay visible — only the round in progress
    # is filtered.
    rounds = {
        "round_1": {"A": _round("strategy1", 3, "msg-A"), "B": _round("strategy2", 0, "msg-B")},
    }
    game = SimpleNamespace(
        current_round=2,
        fake_communication_config=None,
        trust_config=None,
        interaction_graph=None,
        history=_history(rounds),
    )
    gr = GameRound(game)
    view = gr._visible_history(_agent("A"), "choose")
    assert view["round_1"]["B"]["belief"] is None  # key preserved


# ---- Directed field-level filtering -------------------------------------


def _directed_graph():
    # A -> B talk, B -> A see, default none.
    return InteractionGraph.from_config(
        {
            "interaction": {
                "default": "none",
                "edges": [
                    {"from": "A", "to": "B", "level": "talk"},
                    {"from": "B", "to": "A", "level": "see"},
                ],
            }
        },
        ["A", "B", "C"],
    )


def test_see_only_source_keeps_plays_drops_message():
    gr = _make_round(graph=_directed_graph())
    view = gr._visible_history(_agent("A"), "choose")["round_1"]
    # A sees B (B->A see): plays kept, message removed.
    assert view["B"]["strategy"] == "strategy2"
    assert view["B"]["score"] == 0
    assert "message" not in view["B"]
    # C has no edge to A: dropped entirely.
    assert "C" not in view


def test_talk_source_keeps_message():
    gr = _make_round(graph=_directed_graph())
    view = gr._visible_history(_agent("B"), "choose")["round_1"]
    # B sees+hears A (A->B talk): everything, including the message.
    assert view["A"]["strategy"] == "strategy1"
    assert view["A"]["message"] == "msg-A"
    # C has no edge to B: dropped.
    assert "C" not in view


def test_agent_always_sees_own_row_in_full():
    gr = _make_round(graph=_directed_graph())
    view = gr._visible_history(_agent("A"), "choose")["round_1"]
    assert view["A"] == _round("strategy1", 3, "msg-A")


def test_isolated_agent_sees_only_itself():
    gr = _make_round(graph=_directed_graph())
    view = gr._visible_history(_agent("C"), "choose")["round_1"]
    assert set(view.keys()) == {"C"}


# ---- Composition with the trust mechanism -------------------------------


def test_trust_no_look_hides_everything_even_with_graph_edge():
    trust = SimpleNamespace(enabled=True, look_cost=1.0, history_scope="full")
    gr = _make_round(
        graph=_directed_graph(),
        trust_config=trust,
        trust_decisions={"B": NO_LOOK},
    )
    # B would normally see+hear A, but B did not pay to LOOK.
    assert gr._visible_history(_agent("B"), "choose") == {}


def test_trust_look_then_graph_filters():
    trust = SimpleNamespace(enabled=True, look_cost=1.0, history_scope="full")
    gr = _make_round(
        graph=_directed_graph(),
        trust_config=trust,
        trust_decisions={"A": LOOK},
    )
    view = gr._visible_history(_agent("A"), "choose")["round_1"]
    # A paid to LOOK, so trust opens the door; the graph still trims B's
    # message (B->A is see-only) and drops C.
    assert "message" not in view["B"]
    assert "C" not in view


# ---- Prompt opponent scoping --------------------------------------------


def test_get_opponents_scoped_to_visible_neighbours():
    graph = _directed_graph()
    agents = {n: _agent(n) for n in ("A", "B", "C")}
    game = SimpleNamespace(
        current_round=1,
        fake_communication_config=None,
        trust_config=None,
        interaction_graph=graph,
        agents=agents,
        history=_history(),
    )
    gr = GameRound(game)
    # A can see B (B->A see) but not C: only B is a visible opponent.
    names = {o.name for o in gr._get_opponents(agents["A"])}
    assert names == {"B"}


def test_get_opponents_unfiltered_when_complete():
    graph = InteractionGraph.complete(["A", "B", "C"])
    agents = {n: _agent(n) for n in ("A", "B", "C")}
    game = SimpleNamespace(
        current_round=1,
        fake_communication_config=None,
        trust_config=None,
        interaction_graph=graph,
        agents=agents,
        history=_history(),
    )
    gr = GameRound(game)
    names = {o.name for o in gr._get_opponents(agents["A"])}
    assert names == {"B", "C"}
