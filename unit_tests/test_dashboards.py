"""Tests for the relevance-driven Results dashboard (web_api/dashboards.py).

The dashboard picks charts based on what a run actually did: it derives a
context from the run's config + rows, then selects only charts that are
relevant and non-trivial. Row list/dict fields arrive as Python-repr strings
(pandas CSV round-trip), so parsing must tolerate that.
"""

from __future__ import annotations

from web_api.dashboards import build_dashboard, derive_context


def row(**kw):
    base = {
        "game_id": "game_0",
        "language": "en",
        "played_rounds": 1,
        "agent1_name": "agent1",
        "agent2_name": "agent2",
    }
    base.update(kw)
    return base


CFG = {
    "name": "PD",
    "nRounds": 1,
    "languages": ["en"],
    "agents": {"names": ["agent1", "agent2"]},
    "payoffMatrix": {"strategies": {"en": {"strategy1": "OptionA", "strategy2": "OptionB"}}},
}


# ---- context: game shape ---------------------------------------------------


def test_context_counts_games():
    ctx = derive_context(CFG, [row(game_id="game_0"), row(game_id="game_1")])
    assert ctx.n_games == 2


def test_single_round_is_not_repeated():
    ctx = derive_context(CFG, [row(played_rounds=1)])
    assert ctx.max_rounds == 1
    assert ctx.is_repeated is False


def test_multi_round_is_repeated():
    ctx = derive_context(CFG, [row(played_rounds=10)])
    assert ctx.max_rounds == 10
    assert ctx.is_repeated is True


def test_counts_distinct_languages():
    ctx = derive_context(CFG, [row(language="en"), row(language="fr")])
    assert ctx.n_languages == 2
    assert ctx.languages == ["en", "fr"]


def test_single_language_counts_one():
    ctx = derive_context(CFG, [row(language="en"), row(language="en")])
    assert ctx.n_languages == 1


def test_counts_agents_from_name_columns():
    two = derive_context(CFG, [row()])
    assert two.n_agents == 2
    three = derive_context(CFG, [row(agent3_name="agent3")])
    assert three.n_agents == 3


# ---- context: feature detection (data-presence driven) ---------------------


def test_detects_beliefs():
    assert derive_context(CFG, [row()]).has_beliefs is False
    assert derive_context(CFG, [row(agent1_belief_mean_brier=0.3)]).has_beliefs is True


def test_detects_second_order_beliefs_only_when_tom_order_2():
    r1 = row(agent1_belief_mean_brier=0.3, tom_order=1)
    assert derive_context(CFG, [r1]).has_second_order is False
    r2 = row(
        agent1_belief_mean_brier=0.3, tom_order=2, agent1_beliefs_2nd_order="[{'strategy1': 0.5}]"
    )
    assert derive_context(CFG, [r2]).has_second_order is True


def test_detects_trust():
    assert derive_context(CFG, [row()]).has_trust is False
    assert derive_context(CFG, [row(agent1_look_rate=0.5)]).has_trust is True


def test_detects_equilibrium():
    assert derive_context(CFG, [row()]).has_equilibrium is False
    assert derive_context(CFG, [row(equilibrium_rate=1.0)]).has_equilibrium is True


def test_detects_communication_from_flag_or_messages():
    assert derive_context(CFG, [row()]).has_communication is False
    assert derive_context(CFG, [row(agents_communicate=True)]).has_communication is True
    assert derive_context(CFG, [row(agent1_messages="['hello']")]).has_communication is True
    # empty message list must NOT count as communication
    assert derive_context(CFG, [row(agent1_messages="[]")]).has_communication is False


def test_detects_interaction_from_config():
    assert derive_context(CFG, [row()]).has_interaction is False
    cfg = {
        **CFG,
        "interaction": {
            "directed": True,
            "edges": [{"from": "agent1", "to": "agent2", "level": "talk"}],
        },
    }
    assert derive_context(cfg, [row()]).has_interaction is True


def test_detects_tournament_from_config():
    assert derive_context(CFG, [row()]).is_tournament is False
    cfg = {**CFG, "tournament": {"enabled": True, "mode": "round_robin"}}
    assert derive_context(cfg, [row()]).is_tournament is True


def test_counts_seeds():
    assert derive_context(CFG, [row()]).n_seeds == 1
    ctx = derive_context(CFG, [row(seed=1), row(seed=2), row(seed=2)])
    assert ctx.n_seeds == 2


def test_collects_payoff_variants():
    assert derive_context(CFG, [row()]).payoff_variants == []
    ctx = derive_context(CFG, [row(payoff_variant_name="mild"), row(payoff_variant_name="harsh")])
    assert ctx.payoff_variants == ["harsh", "mild"]


# ---- chart selection: which charts appear for which run -------------------


def _ids(spec):
    return {c["id"] for s in spec["sections"] for c in s["charts"]}


def _sections(spec):
    return [s["title"] for s in spec["sections"]]


def _pd_row(**kw):
    return row(
        agent1_strategies="['OptionA']",
        agent1_scores="[6.0]",
        agent2_strategies="['OptionB']",
        agent2_scores="[2.0]",
        welfare_mean_sum=8.0,
        welfare_mean_min=2.0,
        welfare_mean_gini=0.25,
        welfare_efficiency=0.8,
        **kw,
    )


def test_empty_run_yields_no_sections():
    assert build_dashboard(CFG, []) == {"sections": []}


def test_overview_always_present():
    ids = _ids(build_dashboard(CFG, [_pd_row()]))
    assert {"outcome_mix", "score_by_agent", "welfare"} <= ids


def test_single_round_plain_run_has_no_irrelevant_charts():
    ids = _ids(build_dashboard(CFG, [_pd_row(), _pd_row(game_id="game_1")]))
    for absent in (
        "cooperation_trend",
        "belief_brier",
        "look_rate",
        "equilibrium_rate",
        "by_language",
        "interaction_graph",
        "by_payoff_variant",
        "seed_variability",
        "behavior_radar",
    ):
        assert absent not in ids, f"{absent} should not appear for a plain single-round run"


def test_repeated_run_adds_dynamics():
    spec = build_dashboard(CFG, [_pd_row(played_rounds=10)])
    assert "Dynamics" in _sections(spec)
    assert {"cooperation_trend", "score_over_rounds", "welfare_over_rounds"} <= _ids(spec)


def test_multilingual_adds_language_chart_single_language_does_not():
    multi = build_dashboard(CFG, [_pd_row(language="en"), _pd_row(language="fr", game_id="g1")])
    assert "by_language" in _ids(multi)
    single = build_dashboard(CFG, [_pd_row(language="en")])
    assert "by_language" not in _ids(single)


def test_beliefs_run_adds_belief_charts():
    ids = _ids(
        build_dashboard(
            CFG, [_pd_row(agent1_belief_mean_brier=0.3, agent2_belief_mean_brier=0.4, tom_order=1)]
        )
    )
    assert {"belief_brier", "belief_agreement"} <= ids
    assert "belief_second_order" not in ids  # tom_order=1


def test_no_second_order_chart_without_a_scored_metric():
    # Second-order beliefs are stored only as raw distributions (no Brier/score),
    # so there is nothing honest to chart — we must not emit a faked panel.
    ids = _ids(
        build_dashboard(
            CFG,
            [
                _pd_row(
                    agent1_belief_mean_brier=0.3,
                    tom_order=2,
                    agent1_beliefs_2nd_order="[{'strategy1': 0.5, 'strategy2': 0.5}]",
                )
            ],
        )
    )
    assert "belief_second_order" not in ids
    assert "belief_brier" in ids  # first-order accuracy is still shown


def test_trust_run_adds_trust_charts():
    ids = _ids(
        build_dashboard(
            CFG,
            [
                _pd_row(
                    agent1_look_rate=0.5,
                    agent2_look_rate=0.0,
                    agent1_monitoring_cost_total=0.5,
                    agent2_monitoring_cost_total=0.0,
                )
            ],
        )
    )
    assert {"look_rate", "monitoring_cost"} <= ids


def test_equilibrium_run_adds_equilibrium_chart():
    ids = _ids(build_dashboard(CFG, [_pd_row(equilibrium_rate=1.0)]))
    assert "equilibrium_rate" in ids


def test_communication_run_adds_message_chart():
    ids = _ids(
        build_dashboard(
            CFG, [_pd_row(agents_communicate=True, agent1_messages="['let us cooperate']")]
        )
    )
    assert "message_volume" in ids


def test_interaction_config_adds_topology_graph():
    cfg = {
        **CFG,
        "interaction": {
            "directed": True,
            "edges": [
                {"from": "agent1", "to": "agent2", "level": "talk"},
                {"from": "agent2", "to": "agent1", "level": "see"},
            ],
        },
    }
    spec = build_dashboard(cfg, [_pd_row(agents_communicate=True)])
    assert "interaction_graph" in _ids(spec)
    graph = next(c for s in spec["sections"] for c in s["charts"] if c["id"] == "interaction_graph")
    assert graph["kind"] == "graph"
    assert {"nodes", "edges"} <= set(graph)


def test_tournament_config_adds_standings():
    cfg = {**CFG, "tournament": {"enabled": True, "mode": "round_robin"}}
    assert "standings" in _ids(build_dashboard(cfg, [_pd_row()]))


def test_payoff_variants_add_variant_chart():
    rows = [_pd_row(payoff_variant_name="mild"), _pd_row(payoff_variant_name="harsh", game_id="g1")]
    assert "by_payoff_variant" in _ids(build_dashboard(CFG, rows))


def test_multi_seed_adds_variability_chart():
    rows = [_pd_row(seed=1), _pd_row(seed=2, game_id="g1"), _pd_row(seed=3, game_id="g2")]
    assert "seed_variability" in _ids(build_dashboard(CFG, rows))


def test_no_section_is_empty():
    cfg = {**CFG, "interaction": {"edges": [{"from": "agent1", "to": "agent2", "level": "talk"}]}}
    spec = build_dashboard(
        cfg,
        [
            _pd_row(
                played_rounds=5,
                agent1_belief_mean_brier=0.2,
                tom_order=2,
                agents_communicate=True,
                agent1_messages="['hi']",
                equilibrium_rate=0.5,
            )
        ],
    )
    for s in spec["sections"]:
        assert len(s["charts"]) >= 1, f"section {s['title']!r} is empty"


# ---- chart data accuracy ---------------------------------------------------


def _chart_by_id(spec, cid):
    return next(c for s in spec["sections"] for c in s["charts"] if c["id"] == cid)


def test_outcome_mix_counts_joint_plays_across_rounds():
    rows = [
        row(agent1_strategies="['OptionA']", agent2_strategies="['OptionB']"),
        row(game_id="g1", agent1_strategies="['OptionA']", agent2_strategies="['OptionB']"),
        row(game_id="g2", agent1_strategies="['OptionA']", agent2_strategies="['OptionA']"),
    ]
    c = _chart_by_id(build_dashboard(CFG, rows), "outcome_mix")
    data = dict(zip(c["labels"], c["datasets"][0]["data"], strict=True))
    assert data == {"OptionA + OptionB": 2, "OptionA + OptionA": 1}


def test_score_by_agent_is_mean_total_per_agent():
    rows = [
        row(
            agent1_name="agent1", agent2_name="agent2", agent1_scores="[6.0]", agent2_scores="[0.0]"
        ),
        row(
            game_id="g1",
            agent1_name="agent1",
            agent2_name="agent2",
            agent1_scores="[0.0]",
            agent2_scores="[4.0]",
        ),
    ]
    c = _chart_by_id(build_dashboard(CFG, rows), "score_by_agent")
    assert c["labels"] == ["agent1", "agent2"]
    assert c["datasets"][0]["data"] == [3.0, 2.0]


def test_welfare_summarises_efficiency_fairness_inequality():
    rows = [
        row(
            welfare_efficiency=0.8,
            welfare_mean_min=2.0,
            welfare_mean_gini=0.25,
            agent1_scores="[6.0]",
            agent2_scores="[2.0]",
        )
    ]
    c = _chart_by_id(build_dashboard(CFG, rows), "welfare")
    d = dict(zip(c["labels"], c["datasets"][0]["data"], strict=True))
    assert d["Efficiency"] == 0.8
    assert d["Fairness (min score)"] == 2.0
    assert d["Inequality (Gini)"] == 0.25


def test_belief_brier_is_mean_per_agent():
    rows = [
        row(
            agent1_name="agent1",
            agent2_name="agent2",
            agent1_belief_mean_brier=0.3,
            agent2_belief_mean_brier=0.5,
        ),
        row(
            game_id="g1",
            agent1_name="agent1",
            agent2_name="agent2",
            agent1_belief_mean_brier=0.1,
            agent2_belief_mean_brier=0.5,
        ),
    ]
    c = _chart_by_id(build_dashboard(CFG, rows), "belief_brier")
    assert c["labels"] == ["agent1", "agent2"]
    assert c["datasets"][0]["data"] == [0.2, 0.5]


def test_by_language_is_mean_score_per_language():
    rows = [
        row(language="en", agent1_scores="[4.0]", agent2_scores="[4.0]"),
        row(language="fr", game_id="g1", agent1_scores="[2.0]", agent2_scores="[0.0]"),
    ]
    c = _chart_by_id(build_dashboard(CFG, rows), "by_language")
    assert c["labels"] == ["en", "fr"]
    # mean total welfare (sum of agent totals) per language: en=8, fr=2
    assert c["datasets"][0]["data"] == [8.0, 2.0]


def test_look_rate_per_agent():
    rows = [
        row(agent1_name="agent1", agent2_name="agent2", agent1_look_rate=0.5, agent2_look_rate=0.0)
    ]
    c = _chart_by_id(build_dashboard(CFG, rows), "look_rate")
    assert c["labels"] == ["agent1", "agent2"]
    assert c["datasets"][0]["data"] == [0.5, 0.0]


def test_message_volume_counts_messages_per_agent():
    rows = [
        row(
            agent1_name="agent1",
            agent2_name="agent2",
            agents_communicate=True,
            agent1_messages="['a','b']",
            agent2_messages="['c']",
        )
    ]
    c = _chart_by_id(build_dashboard(CFG, rows), "message_volume")
    assert c["labels"] == ["agent1", "agent2"]
    assert c["datasets"][0]["data"] == [2, 1]


def test_cooperation_trend_is_signed_strategy_per_round_per_agent():
    # Paper convention: strategy1 (Option A) = +1, strategy2 (Option B) = -1.
    rows = [
        row(
            played_rounds=2,
            agent1_strategies="['OptionA','OptionB']",
            agent2_strategies="['OptionA','OptionA']",
        )
    ]
    c = _chart_by_id(build_dashboard(CFG, rows), "cooperation_trend")
    assert c["kind"] == "line"
    assert c["labels"] == ["R1", "R2"]
    series = {d["label"]: d["data"] for d in c["datasets"]}
    assert series["agent1"] == [1.0, -1.0]
    assert series["agent2"] == [1.0, 1.0]


# ---- radar + top-messages (paper-style representations) ---------------------


def test_behavior_radar_appears_when_at_least_three_axes():
    # cooperation + score are always available; a third axis (beliefs) unlocks it.
    plain = build_dashboard(CFG, [_pd_row()])
    assert "behavior_radar" not in _ids(plain)  # only 2 axes -> no radar
    withbelief = build_dashboard(
        CFG, [_pd_row(agent1_belief_mean_brier=0.2, agent2_belief_mean_brier=0.4)]
    )
    r = _chart_by_id(withbelief, "behavior_radar")
    assert r["kind"] == "radar"
    assert r["labels"] == ["Cooperation", "Score", "Belief accuracy"]
    series = {d["label"]: d["data"] for d in r["datasets"]}
    # agent1: coop=1.0 (OptionA), score norm=6/6=1.0, acc=1-0.2=0.8
    assert series["agent1"] == [1.0, 1.0, 0.8]
    # agent2: coop=0.0 (OptionB), score norm=2/6, acc=1-0.4=0.6
    assert series["agent2"] == [0.0, round(2 / 6, 6), 0.6]


def test_cooperation_radar_across_personality_combos():
    rows = [
        row(
            agent1_personality="coop",
            agent2_personality="coop",
            agent1_strategies="['OptionA']",
            agent2_strategies="['OptionA']",
        ),
        row(
            game_id="g1",
            agent1_personality="coop",
            agent2_personality="selfish",
            agent1_strategies="['OptionA']",
            agent2_strategies="['OptionB']",
        ),
        row(
            game_id="g2",
            agent1_personality="selfish",
            agent2_personality="selfish",
            agent1_strategies="['OptionB']",
            agent2_strategies="['OptionB']",
        ),
    ]
    r = _chart_by_id(build_dashboard(CFG, rows), "cooperation_radar")
    assert r["kind"] == "radar"
    d = dict(zip(r["labels"], r["datasets"][0]["data"], strict=True))
    assert d == {"coop + coop": 1.0, "coop + selfish": 0.5, "selfish + selfish": 0.0}


def test_top_messages_ranks_messages_per_agent():
    rows = [
        row(agents_communicate=True, agent1_messages="['hi','hi','yo']", agent2_messages="['hi']")
    ]
    c = _chart_by_id(build_dashboard(CFG, rows), "top_messages")
    assert c["kind"] == "bar"
    assert c["labels"] == ["hi", "yo"]
    series = {d["label"]: d["data"] for d in c["datasets"]}
    assert series["agent1"] == [2, 1]
    assert series["agent2"] == [1, 0]


# ---- remaining chart data --------------------------------------------------


def test_score_over_rounds_is_cumulative_per_agent():
    rows = [
        row(
            played_rounds=3,
            agent1_name="agent1",
            agent2_name="agent2",
            agent1_scores="[1.0,2.0,3.0]",
            agent2_scores="[0.0,0.0,5.0]",
        )
    ]
    c = _chart_by_id(build_dashboard(CFG, rows), "score_over_rounds")
    assert c["labels"] == ["R1", "R2", "R3"]
    series = {d["label"]: d["data"] for d in c["datasets"]}
    assert series["agent1"] == [1.0, 3.0, 6.0]
    assert series["agent2"] == [0.0, 0.0, 5.0]


def test_welfare_over_rounds_uses_per_round_sum():
    rows = [row(played_rounds=2, welfare_per_round="[{'sum': 4.0}, {'sum': 6.0}]")]
    c = _chart_by_id(build_dashboard(CFG, rows), "welfare_over_rounds")
    assert c["labels"] == ["R1", "R2"]
    assert c["datasets"][0]["data"] == [4.0, 6.0]


def test_belief_agreement_is_mean_per_agent():
    rows = [
        row(
            agent1_name="agent1",
            agent2_name="agent2",
            agent1_belief_mean_brier=0.2,
            agent2_belief_mean_brier=0.2,
            agent1_belief_agreement_rate=1.0,
            agent2_belief_agreement_rate=0.0,
        )
    ]
    c = _chart_by_id(build_dashboard(CFG, rows), "belief_agreement")
    assert c["labels"] == ["agent1", "agent2"]
    assert c["datasets"][0]["data"] == [1.0, 0.0]


def test_equilibrium_rate_is_mean():
    rows = [_pd_row(equilibrium_rate=1.0), _pd_row(game_id="g1", equilibrium_rate=0.0)]
    c = _chart_by_id(build_dashboard(CFG, rows), "equilibrium_rate")
    assert c["datasets"][0]["data"] == [0.5]


def test_monitoring_cost_is_mean_per_agent():
    rows = [
        _pd_row(
            agent1_look_rate=0.5,
            agent2_look_rate=0.0,
            agent1_monitoring_cost_total=0.5,
            agent2_monitoring_cost_total=0.0,
        )
    ]
    c = _chart_by_id(build_dashboard(CFG, rows), "monitoring_cost")
    assert c["labels"] == ["agent1", "agent2"]
    assert c["datasets"][0]["data"] == [0.5, 0.0]


def test_by_payoff_variant_is_mean_welfare_per_variant():
    rows = [
        row(payoff_variant_name="mild", agent1_scores="[3.0]", agent2_scores="[3.0]"),
        row(
            payoff_variant_name="harsh", game_id="g1", agent1_scores="[1.0]", agent2_scores="[1.0]"
        ),
    ]
    c = _chart_by_id(build_dashboard(CFG, rows), "by_payoff_variant")
    assert c["labels"] == ["harsh", "mild"]
    assert c["datasets"][0]["data"] == [2.0, 6.0]


def test_seed_variability_is_mean_welfare_per_seed():
    rows = [
        row(seed=1, agent1_scores="[4.0]", agent2_scores="[4.0]"),
        row(seed=2, game_id="g1", agent1_scores="[1.0]", agent2_scores="[1.0]"),
    ]
    c = _chart_by_id(build_dashboard(CFG, rows), "seed_variability")
    assert c["labels"] == ["1", "2"]
    assert c["datasets"][0]["data"] == [8.0, 2.0]


# ---- personality-combo comparison ------------------------------------------


def test_context_counts_personality_combos():
    same = [
        row(agent1_personality="coop", agent2_personality="coop"),
        row(game_id="g1", agent1_personality="coop", agent2_personality="coop"),
    ]
    assert derive_context(CFG, same).n_personality_combos == 1
    varied = [
        row(agent1_personality="coop", agent2_personality="selfish"),
        row(game_id="g1", agent1_personality="selfish", agent2_personality="selfish"),
    ]
    assert derive_context(CFG, varied).n_personality_combos == 2


def test_by_personality_only_when_multiple_combos():
    varied = [
        row(
            agent1_personality="coop",
            agent2_personality="selfish",
            agent1_scores="[6.0]",
            agent2_scores="[0.0]",
        ),
        row(
            game_id="g1",
            agent1_personality="selfish",
            agent2_personality="selfish",
            agent1_scores="[2.0]",
            agent2_scores="[2.0]",
        ),
    ]
    assert "by_personality" in _ids(build_dashboard(CFG, varied))
    single = [_pd_row(agent1_personality="coop", agent2_personality="coop")]
    assert "by_personality" not in _ids(build_dashboard(CFG, single))


def test_by_personality_is_mean_welfare_per_combo():
    rows = [
        row(
            agent1_personality="coop",
            agent2_personality="selfish",
            agent1_scores="[6.0]",
            agent2_scores="[0.0]",
        ),
        row(
            game_id="g1",
            agent1_personality="selfish",
            agent2_personality="selfish",
            agent1_scores="[2.0]",
            agent2_scores="[2.0]",
        ),
    ]
    c = _chart_by_id(build_dashboard(CFG, rows), "by_personality")
    d = dict(zip(c["labels"], c["datasets"][0]["data"], strict=True))
    assert d == {"coop + selfish": 6.0, "selfish + selfish": 4.0}
