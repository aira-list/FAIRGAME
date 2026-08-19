"""Tests for the agent interaction graph (visibility + communication).

The graph is a single *directed* graph whose edges carry one of three
ordinal levels: ``none`` < ``see`` < ``talk`` (``talk`` subsumes ``see``).

Direction convention: an edge ``A -> B`` means information flows from ``A``
to ``B`` — i.e. ``B`` *perceives* ``A``. A ``see`` edge lets ``B`` observe
``A``'s plays; a ``talk`` edge additionally delivers ``A``'s messages to
``B``.
"""

from __future__ import annotations

import pytest

from src.communication.interaction import NONE, SEE, TALK, InteractionGraph

# ---- Defaults / backward compatibility ----------------------------------


def test_no_block_yields_complete_graph():
    g = InteractionGraph.from_config({}, ["a", "b", "c"])
    assert g.is_fully_connected
    for viewer in ("a", "b", "c"):
        for source in ("a", "b", "c"):
            assert g.sees(viewer, source)
            assert g.hears(viewer, source)


def test_complete_factory_is_fully_connected():
    g = InteractionGraph.complete(["a", "b"])
    assert g.is_fully_connected
    assert g.sees("a", "b") and g.hears("a", "b")
    assert g.sees("b", "a") and g.hears("b", "a")


def test_falsy_block_yields_complete_graph():
    assert InteractionGraph.from_config({"interaction": None}, ["a", "b"]).is_fully_connected


# ---- Direction + ordinal levels -----------------------------------------


def _directed_graph():
    # A -> B talk  (B perceives A fully, incl. messages)
    # B -> A see   (A observes B's plays only)
    # everything else: none (default)
    return InteractionGraph.from_config(
        {
            "interaction": {
                "directed": True,
                "default": "none",
                "edges": [
                    {"from": "A", "to": "B", "level": "talk"},
                    {"from": "B", "to": "A", "level": "see"},
                ],
            }
        },
        ["A", "B", "C"],
    )


def test_directed_talk_edge_grants_see_and_hear_to_target():
    g = _directed_graph()
    # B is the target of A->B(talk): B perceives A fully.
    assert g.sees("B", "A")
    assert g.hears("B", "A")


def test_directed_see_edge_grants_visibility_not_messages():
    g = _directed_graph()
    # A is the target of B->A(see): A observes B's plays but not messages.
    assert g.sees("A", "B")
    assert not g.hears("A", "B")


def test_talk_subsumes_see():
    g = _directed_graph()
    assert g.level("A", "B") == TALK
    # talk implies the viewer both sees and hears the source.
    assert g.sees("B", "A") and g.hears("B", "A")


def test_default_level_applies_to_unlisted_pairs():
    g = _directed_graph()
    # No edge touches C, default is none.
    assert not g.sees("C", "A")
    assert not g.sees("A", "C")
    assert not g.hears("C", "B")


def test_default_see_makes_everyone_visible_but_silent():
    g = InteractionGraph.from_config({"interaction": {"default": "see"}}, ["a", "b", "c"])
    assert not g.is_fully_connected
    assert g.sees("a", "b")
    assert not g.hears("a", "b")


# ---- Self edges ----------------------------------------------------------


def test_agent_always_perceives_itself():
    g = InteractionGraph.from_config({"interaction": {"default": "none"}}, ["a", "b"])
    assert g.sees("a", "a")
    assert g.hears("a", "a")


def test_self_edges_in_config_are_ignored():
    g = InteractionGraph.from_config(
        {"interaction": {"default": "none", "edges": [{"from": "a", "to": "a", "level": "talk"}]}},
        ["a", "b"],
    )
    # Still fine; self is implicitly full and the explicit self edge is dropped.
    assert g.sees("a", "a") and g.hears("a", "a")


# ---- Undirected shortcut -------------------------------------------------


def test_undirected_mirrors_edges():
    g = InteractionGraph.from_config(
        {
            "interaction": {
                "directed": False,
                "default": "none",
                "edges": [{"from": "A", "to": "B", "level": "talk"}],
            }
        },
        ["A", "B"],
    )
    assert g.sees("A", "B") and g.hears("A", "B")
    assert g.sees("B", "A") and g.hears("B", "A")


# ---- Validation ----------------------------------------------------------


def test_unknown_endpoint_rejected():
    with pytest.raises(ValueError):
        InteractionGraph.from_config(
            {"interaction": {"edges": [{"from": "A", "to": "Z", "level": "talk"}]}},
            ["A", "B"],
        )


def test_bad_level_rejected():
    with pytest.raises(ValueError):
        InteractionGraph.from_config(
            {"interaction": {"edges": [{"from": "A", "to": "B", "level": "whisper"}]}},
            ["A", "B"],
        )


def test_bad_default_rejected():
    with pytest.raises(ValueError):
        InteractionGraph.from_config({"interaction": {"default": "whisper"}}, ["A", "B"])


# ---- Reduced connectivity flips is_fully_connected -----------------------


def test_any_reduced_edge_is_not_fully_connected():
    g = InteractionGraph.from_config(
        {"interaction": {"default": "talk", "edges": [{"from": "A", "to": "B", "level": "see"}]}},
        ["A", "B"],
    )
    assert not g.is_fully_connected


# ---- Serialisation -------------------------------------------------------


def test_to_dict_roundtrips_levels():
    g = _directed_graph()
    d = g.to_dict()
    assert d["directed"] is True
    levels = {(e["from"], e["to"]): e["level"] for e in d["edges"]}
    assert levels[("A", "B")] == TALK
    assert levels[("B", "A")] == SEE


def test_level_constants():
    assert (NONE, SEE, TALK) == ("none", "see", "talk")
