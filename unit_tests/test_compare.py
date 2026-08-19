"""Tests for the adaptive cross-run Compare view (web_api/compare.py).

Comparison must never break for any selection of runs. It derives a context
(what varies across the selection: models / scenarios / languages / payoff
types / rounds), picks a primary grouping dimension, and emits only the charts
whose data is available across the whole selection — the robustness-radar axes
(I_V, C_I, S_P, V_R) are each included only when the data supports them.
"""

from __future__ import annotations

from web_api.compare import (
    build_comparison,
    compute_group_stats,
    derive_compare_context,
)


def cfg(name="PD"):
    return {
        "name": name,
        "payoffMatrix": {"strategies": {"en": {"strategy1": "OptionA", "strategy2": "OptionB"}}},
    }


def rrow(model, **kw):
    base = {
        "game_id": "g",
        "language": "en",
        "played_rounds": 1,
        "agent1_name": "a1",
        "agent1_llm": model,
        "agent1_scores": "[3.0]",
        "agent2_name": "a2",
        "agent2_llm": model,
        "agent2_scores": "[3.0]",
        "agent1_strategies": "['OptionA']",
        "agent2_strategies": "['OptionA']",
    }
    base.update(kw)
    return base


def run(rows, name="PD"):
    return {"config": cfg(name), "rows": rows}


def _ids(spec):
    return {c["id"] for s in spec["sections"] for c in s["charts"]}


def _chart(spec, cid):
    return next(c for s in spec["sections"] for c in s["charts"] if c["id"] == cid)


# ---- context: what varies, primary dimension, available radar axes ---------


def test_primary_is_model_when_models_vary():
    ctx = derive_compare_context([run([rrow("A")]), run([rrow("B")])])
    assert set(ctx.models) == {"A", "B"}
    assert ctx.primary == "model"


def test_primary_is_scenario_when_only_games_vary():
    ctx = derive_compare_context([run([rrow("A")], name="PD"), run([rrow("A")], name="Stag")])
    assert ctx.primary == "scenario"


def test_axes_only_include_computable_metrics():
    # single round, single language, no payoff variants -> only I_V
    ctx = derive_compare_context([run([rrow("A")]), run([rrow("B")])])
    assert ctx.axes == ["I_V"]


def test_axes_grow_with_languages_rounds_and_variants():
    rows = [
        rrow(
            "A",
            language="en",
            played_rounds=2,
            agent1_strategies="['OptionA','OptionB']",
            agent2_strategies="['OptionA','OptionA']",
            payoff_variant_name="mild",
        ),
        rrow("A", language="fr", game_id="g1", payoff_variant_name="harsh"),
    ]
    ctx = derive_compare_context([run(rows)])
    assert ctx.axes == ["I_V", "C_I", "S_P", "V_R"]


# ---- group stats -----------------------------------------------------------


def test_group_stats_cooperation_and_payoff_by_model():
    runs = [
        run(
            [
                rrow(
                    "A",
                    agent1_strategies="['OptionA']",
                    agent2_strategies="['OptionB']",
                    agent1_scores="[6.0]",
                    agent2_scores="[0.0]",
                )
            ]
        ),
        run(
            [
                rrow(
                    "B",
                    agent1_strategies="['OptionB']",
                    agent2_strategies="['OptionB']",
                    agent1_scores="[2.0]",
                    agent2_scores="[2.0]",
                )
            ]
        ),
    ]
    stats = compute_group_stats(runs, "model")
    assert stats["A"]["cooperation"] == 0.5  # one OptionA, one OptionB
    assert stats["A"]["payoff"] == 6.0  # final_sum = 6 + 0
    assert stats["B"]["cooperation"] == 0.0
    assert stats["B"]["payoff"] == 4.0


def test_group_stats_by_scenario():
    runs = [run([rrow("A")], name="PD"), run([rrow("A")], name="Stag")]
    stats = compute_group_stats(runs, "scenario")
    assert set(stats) == {"PD", "Stag"}


# ---- adaptive chart selection ----------------------------------------------


def test_always_has_cooperation_and_payoff_comparison():
    ids = _ids(
        build_comparison(
            [
                run([rrow("A")]),
                run(
                    [
                        rrow(
                            "B",
                            agent1_strategies="['OptionB']",
                            agent2_strategies="['OptionB']",
                            agent1_scores="[1.0]",
                            agent2_scores="[1.0]",
                        )
                    ]
                ),
            ]
        )
    )
    assert {"compare_cooperation", "compare_payoff"} <= ids


def test_no_radar_when_fewer_than_three_axes():
    # single round / single language / no variants -> only I_V -> no radar
    ids = _ids(build_comparison([run([rrow("A")]), run([rrow("B")])]))
    assert "robustness_radar" not in ids


def test_radar_appears_with_three_or_more_axes():
    rows_a = [
        rrow(
            "A",
            language="en",
            played_rounds=2,
            payoff_variant_name="mild",
            agent1_strategies="['OptionA','OptionB']",
            agent2_strategies="['OptionA','OptionA']",
        ),
        rrow(
            "A",
            language="fr",
            game_id="g1",
            played_rounds=2,
            payoff_variant_name="harsh",
            agent1_strategies="['OptionB','OptionB']",
            agent2_strategies="['OptionA','OptionA']",
        ),
    ]
    rows_b = [
        rrow(
            "B",
            language="en",
            played_rounds=2,
            payoff_variant_name="mild",
            agent1_strategies="['OptionA','OptionA']",
            agent2_strategies="['OptionA','OptionA']",
        ),
        rrow(
            "B",
            language="fr",
            game_id="g1",
            played_rounds=2,
            payoff_variant_name="harsh",
            agent1_strategies="['OptionB','OptionB']",
            agent2_strategies="['OptionB','OptionB']",
        ),
    ]
    spec = build_comparison([run(rows_a), run(rows_b)])
    r = _chart(spec, "robustness_radar")
    assert r["kind"] == "radar"
    assert r["labels"] == ["I_V", "C_I", "S_P", "V_R"]
    assert {d["label"] for d in r["datasets"]} == {"A", "B"}


def test_cross_game_comparison_groups_by_scenario():
    spec = build_comparison(
        [
            run(
                [rrow("A", agent1_strategies="['OptionA']", agent2_strategies="['OptionA']")],
                name="PD",
            ),
            run(
                [rrow("A", agent1_strategies="['OptionB']", agent2_strategies="['OptionB']")],
                name="Stag",
            ),
        ]
    )
    c = _chart(spec, "compare_cooperation")
    d = dict(zip(c["labels"], c["datasets"][0]["data"], strict=True))
    assert d == {"PD": 1.0, "Stag": 0.0}


def test_no_language_chart_when_single_language():
    mono = build_comparison([run([rrow("A")]), run([rrow("B")])])
    assert "payoff_by_language" not in _ids(mono)


def test_single_model_multilingual_compares_by_language_directly():
    # Only language varies -> primary is language; compare_payoff IS the
    # language comparison, so no separate (degenerate) payoff_by_language chart.
    spec = build_comparison(
        [
            run(
                [
                    rrow("A", language="en"),
                    rrow("A", language="fr", game_id="g1", agent1_scores="[5.0]"),
                ]
            )
        ]
    )
    assert "payoff_by_language" not in _ids(spec)
    assert _chart(spec, "compare_payoff")["labels"] == ["en", "fr"]


def test_cross_model_multilingual_groups_language_by_model():
    # Models vary AND languages vary -> payoff_by_language grouped by MODEL.
    spec = build_comparison(
        [
            run(
                [
                    rrow("A", language="en", agent1_scores="[4.0]", agent2_scores="[4.0]"),
                    rrow(
                        "A",
                        language="fr",
                        game_id="g1",
                        agent1_scores="[2.0]",
                        agent2_scores="[2.0]",
                    ),
                ]
            ),
            run(
                [
                    rrow("B", language="en", agent1_scores="[1.0]", agent2_scores="[1.0]"),
                    rrow(
                        "B",
                        language="fr",
                        game_id="g1",
                        agent1_scores="[3.0]",
                        agent2_scores="[3.0]",
                    ),
                ]
            ),
        ]
    )
    c = _chart(spec, "payoff_by_language")
    assert c["labels"] == ["en", "fr"]
    series = {d["label"]: d["data"] for d in c["datasets"]}
    assert set(series) == {"A", "B"}  # one series per MODEL
    assert series["A"] == [8.0, 4.0]  # A: en=4+4, fr=2+2
    assert series["B"] == [2.0, 6.0]  # B: en=1+1, fr=3+3


def test_dynamics_only_when_all_runs_repeated():
    mixed = build_comparison(
        [
            run(
                [
                    rrow(
                        "A",
                        played_rounds=2,
                        agent1_strategies="['OptionA','OptionB']",
                        agent2_strategies="['OptionA','OptionA']",
                    )
                ]
            ),
            run([rrow("B")]),
        ]
    )  # B is single-round
    assert "strategy_trend" not in _ids(mixed)
    allrep = build_comparison(
        [
            run(
                [
                    rrow(
                        "A",
                        played_rounds=2,
                        agent1_strategies="['OptionA','OptionB']",
                        agent2_strategies="['OptionA','OptionA']",
                    )
                ]
            ),
            run(
                [
                    rrow(
                        "B",
                        played_rounds=2,
                        agent1_strategies="['OptionA','OptionA']",
                        agent2_strategies="['OptionA','OptionA']",
                    )
                ]
            ),
        ]
    )
    assert "strategy_trend" in _ids(allrep)


def test_heterogeneous_selection_does_not_break():
    # different games, different models, different round counts, one multilingual
    runs = [
        run([rrow("A", language="en")], name="PD"),
        run(
            [
                rrow(
                    "B",
                    language="fr",
                    played_rounds=2,
                    agent1_strategies="['OptionA','OptionB']",
                    agent2_strategies="['OptionA','OptionA']",
                )
            ],
            name="Stag",
        ),
        run(
            [rrow("A", payoff_variant_name="harsh", agent1_scores="[9.0]")],
            name="Snowdrift",
        ),
    ]
    spec = build_comparison(runs)  # must not raise
    assert "compare_payoff" in _ids(spec)


def test_empty_comparison_is_empty():
    assert build_comparison([]) == {"sections": []}


def test_single_group_comparison_has_no_trivial_bars():
    # One group means one bar per chart — a number, not a comparison.
    # The spec comes back well-formed but chartless.
    spec = build_comparison([run([rrow("A")])])
    assert spec["sections"] == []
