"""Relevance-driven Results dashboard.

Given a run's config + result rows, derive a :class:`Context` describing what
the run actually did, then select only the charts that are relevant and
non-trivial. The frontend renders whatever chart specs this module emits, so
the "which charts should this run show" decision lives here where it is tested.

Rows arrive as native JSON (list cells are real lists); :func:`as_list` also
tolerates the Python-repr strings that legacy CSV-only runs produce. Column
names come from :mod:`src.results_processing.row_schema`.
"""

from __future__ import annotations

import ast
import math
from dataclasses import dataclass, field
from typing import Any

from src.results_processing.row_schema import AgentCol, agent_col

_MAX_AGENTS = 12  # upper bound when scanning agent{i}_* columns


def as_list(val: Any) -> list:
    """Parse a list-ish value that may be a real list or a Python-repr string."""
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return []
        try:
            parsed = ast.literal_eval(s)
        except (ValueError, SyntaxError):
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def is_missing(v: Any) -> bool:
    if v is None or v == "":
        return True
    return bool(isinstance(v, float) and math.isnan(v))


def column_present(rows: list[dict[str, Any]], col: str) -> bool:
    """True if any row carries a non-missing value for ``col``."""
    return any(col in r and not is_missing(r[col]) for r in rows)


def truthy(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in {"1", "true", "yes", "on"}
    return bool(v) and not is_missing(v)


def _count_agents(rows: list[dict[str, Any]]) -> int:
    n = 0
    for i in range(1, _MAX_AGENTS + 1):
        if column_present(rows, agent_col(i, AgentCol.NAME)):
            n = i
        else:
            break
    return n


@dataclass
class Context:
    n_games: int = 0
    max_rounds: int = 1
    is_repeated: bool = False
    languages: list[str] = field(default_factory=list)
    n_languages: int = 0
    n_agents: int = 0
    tom_order: int = 0
    has_beliefs: bool = False
    has_second_order: bool = False
    has_trust: bool = False
    has_equilibrium: bool = False
    has_communication: bool = False
    has_interaction: bool = False
    is_tournament: bool = False
    n_seeds: int = 1
    payoff_variants: list[str] = field(default_factory=list)
    n_personality_combos: int = 0


def derive_context(config: dict[str, Any], rows: list[dict[str, Any]]) -> Context:
    config = config or {}
    rows = rows or []
    n_agents = _count_agents(rows)

    def any_agent(suffix: str) -> bool:
        return any(
            column_present(rows, agent_col(i, suffix)) for i in range(1, max(n_agents, 1) + 1)
        )

    languages = sorted({r["language"] for r in rows if not is_missing(r.get("language"))})
    max_rounds = max((int(r.get("played_rounds") or 1) for r in rows), default=1)
    tom_order = max((int(r.get("tom_order") or 0) for r in rows), default=0)

    seeds = {r["seed"] for r in rows if "seed" in r and not is_missing(r["seed"])}
    variants = sorted(
        {r["payoff_variant_name"] for r in rows if not is_missing(r.get("payoff_variant_name"))}
    )

    combos = set()
    for r in rows:
        combo = tuple(
            str(r.get(agent_col(i, AgentCol.PERSONALITY)))
            for i in range(1, max(n_agents, 1) + 1)
            if not is_missing(r.get(agent_col(i, AgentCol.PERSONALITY)))
        )
        if combo:
            combos.add(combo)

    has_comm = any(truthy(r.get("agents_communicate")) for r in rows) or any(
        as_list(r.get(agent_col(i, AgentCol.MESSAGES)))
        for r in rows
        for i in range(1, max(n_agents, 1) + 1)
    )

    return Context(
        n_games=len(rows),
        max_rounds=max_rounds,
        is_repeated=max_rounds > 1,
        languages=languages,
        n_languages=len(languages),
        n_agents=n_agents,
        tom_order=tom_order,
        has_beliefs=any_agent(AgentCol.BELIEF_MEAN_BRIER),
        has_second_order=tom_order >= 2 and any_agent(AgentCol.BELIEFS_2ND_ORDER),
        has_trust=any_agent(AgentCol.LOOK_RATE),
        has_equilibrium=column_present(rows, "equilibrium_rate"),
        has_communication=bool(has_comm),
        has_interaction=bool((config.get("interaction") or {}).get("edges")),
        is_tournament=bool((config.get("tournament") or {}).get("enabled")),
        n_seeds=len(seeds) or 1,
        payoff_variants=variants,
        n_personality_combos=len(combos),
    )


def chart_spec(cid: str, kind: str, title: str, **extra: Any) -> dict[str, Any]:
    ch = {"id": cid, "kind": kind, "title": title, "labels": [], "datasets": []}
    ch.update(extra)
    return ch


def _interaction_graph(config: dict[str, Any]) -> dict[str, Any]:
    names = (config.get("agents") or {}).get("names") or []
    edges = (config.get("interaction") or {}).get("edges") or []
    nodes = [{"id": n} for n in names]
    clean_edges = [
        {"from": e.get("from"), "to": e.get("to"), "level": e.get("level", "see")} for e in edges
    ]
    return chart_spec(
        "interaction_graph",
        "graph",
        "Interaction topology",
        nodes=nodes,
        edges=clean_edges,
        description="Who observes (see) or messages (talk) whom.",
    )


def as_float(v: Any):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def mean_of(xs: list[Any]) -> float:
    vals = [x for x in xs if x is not None]
    return round(sum(vals) / len(vals), 6) if vals else 0.0


def _agent_names(rows: list[dict[str, Any]], n: int) -> list[str]:
    out = []
    for i in range(1, n + 1):
        nm = next(
            (
                r.get(agent_col(i, AgentCol.NAME))
                for r in rows
                if not is_missing(r.get(agent_col(i, AgentCol.NAME)))
            ),
            None,
        )
        out.append(str(nm) if nm is not None else f"agent{i}")
    return out


def _game_total(r: dict[str, Any], i: int) -> float:
    return sum(
        v
        for v in (as_float(x) for x in as_list(r.get(agent_col(i, AgentCol.SCORES))))
        if v is not None
    )


def _c_outcome_mix(rows, n):
    from collections import Counter

    cnt: Counter = Counter()
    for r in rows:
        strat = [as_list(r.get(agent_col(i, AgentCol.STRATEGIES))) for i in range(1, n + 1)]
        for idx in range(max((len(s) for s in strat), default=0)):
            combo = [str(s[idx]) for s in strat if idx < len(s)]
            if len(combo) == n:
                cnt[" + ".join(combo)] += 1
    items = sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))
    return chart_spec(
        "outcome_mix",
        "bar",
        "Outcome mix",
        labels=[k for k, _ in items],
        datasets=[{"label": "games × rounds", "data": [v for _, v in items]}],
    )


def _c_score_by_agent(rows, n, names):
    data = [mean_of([_game_total(r, i) for r in rows]) for i in range(1, n + 1)]
    return chart_spec(
        "score_by_agent",
        "bar",
        "Mean score by agent",
        labels=names,
        datasets=[{"label": "mean total score", "data": data}],
    )


def _c_welfare(rows):
    return chart_spec(
        "welfare",
        "bar",
        "Welfare",
        labels=["Efficiency", "Fairness (min score)", "Inequality (Gini)"],
        datasets=[
            {
                "label": "mean",
                "data": [
                    mean_of([as_float(r.get("welfare_efficiency")) for r in rows]),
                    mean_of([as_float(r.get("welfare_mean_min")) for r in rows]),
                    mean_of([as_float(r.get("welfare_mean_gini")) for r in rows]),
                ],
            }
        ],
    )


def _c_belief_brier(rows, n, names):
    data = [
        mean_of([as_float(r.get(agent_col(i, AgentCol.BELIEF_MEAN_BRIER))) for r in rows])
        for i in range(1, n + 1)
    ]
    return chart_spec(
        "belief_brier",
        "bar",
        "Belief accuracy (Brier — lower is better)",
        labels=names,
        datasets=[{"label": "mean Brier", "data": data}],
    )


def _c_by_language(rows):
    from collections import defaultdict

    langs = sorted({r.get("language") for r in rows if not is_missing(r.get("language"))})
    by = defaultdict(list)
    for r in rows:
        na = _count_agents([r])
        by[r.get("language")].append(sum(_game_total(r, i) for i in range(1, na + 1)))
    return chart_spec(
        "by_language",
        "bar",
        "Welfare by language",
        labels=langs,
        datasets=[{"label": "mean welfare", "data": [mean_of(by[lang]) for lang in langs]}],
    )


def _c_look_rate(rows, n, names):
    data = [
        mean_of([as_float(r.get(agent_col(i, AgentCol.LOOK_RATE))) for r in rows])
        for i in range(1, n + 1)
    ]
    return chart_spec(
        "look_rate",
        "bar",
        "Monitoring (LOOK) rate by agent",
        labels=names,
        datasets=[{"label": "LOOK rate", "data": data}],
    )


def _c_message_volume(rows, n, names):
    data = [
        sum(len(as_list(r.get(agent_col(i, AgentCol.MESSAGES)))) for r in rows)
        for i in range(1, n + 1)
    ]
    return chart_spec(
        "message_volume",
        "bar",
        "Message volume by agent",
        labels=names,
        datasets=[{"label": "messages", "data": data}],
    )


def strategy_value_map(config: dict[str, Any]) -> dict[str, float]:
    """Map each strategy display label to the paper's signed value:
    strategy1 (Option A / cooperate) = +1, strategy2 = -1."""
    strat = (config.get("payoffMatrix") or {}).get("strategies") or {}
    m: dict[str, float] = {}
    for d in strat.values():
        if isinstance(d, dict):
            if d.get("strategy1") is not None:
                m[str(d["strategy1"])] = 1.0
            if d.get("strategy2") is not None:
                m[str(d["strategy2"])] = -1.0
    return m


def _coop_share(rows, i, vmap) -> float:
    plays = []
    for r in rows:
        for s in as_list(r.get(agent_col(i, AgentCol.STRATEGIES))):
            v = vmap.get(str(s))
            if v is not None:
                plays.append(1.0 if v > 0 else 0.0)
    return mean_of(plays)


def _c_cooperation_trend(config, rows, n, names, max_rounds):
    vmap = strategy_value_map(config)
    if not vmap:
        return None
    datasets = []
    for i in range(1, n + 1):
        data = []
        for idx in range(max_rounds):
            vals = []
            for r in rows:
                strat = as_list(r.get(agent_col(i, AgentCol.STRATEGIES)))
                if idx < len(strat) and str(strat[idx]) in vmap:
                    vals.append(vmap[str(strat[idx])])
            data.append(mean_of(vals))
        datasets.append({"label": names[i - 1], "data": data})
    return chart_spec(
        "cooperation_trend",
        "line",
        "Strategy value over rounds (+1 = Option A, -1 = Option B)",
        labels=_round_labels(max_rounds),
        datasets=datasets,
    )


def _c_behavior_radar(config, rows, n, names):
    vmap = strategy_value_map(config)
    if not vmap:
        return None
    axes = ["Cooperation", "Score"]
    coop = [_coop_share(rows, i, vmap) for i in range(1, n + 1)]
    totals = [mean_of([_game_total(r, i) for r in rows]) for i in range(1, n + 1)]
    mx = max(totals) if totals else 0
    score_norm = [round(t / mx, 6) if mx else 0.0 for t in totals]
    per_agent = [[coop[i - 1], score_norm[i - 1]] for i in range(1, n + 1)]

    if any(column_present(rows, agent_col(i, AgentCol.BELIEF_MEAN_BRIER)) for i in range(1, n + 1)):
        axes.append("Belief accuracy")
        for i in range(1, n + 1):
            briers = [as_float(r.get(agent_col(i, AgentCol.BELIEF_MEAN_BRIER))) for r in rows]
            briers = [b for b in briers if b is not None]
            # An agent with no belief data gets a null point — the perfect
            # accuracy that ``1.0 - mean_of([]) == 1.0`` would imply is wrong.
            per_agent[i - 1].append(round(max(0.0, 1.0 - mean_of(briers)), 6) if briers else None)
    if any(column_present(rows, agent_col(i, AgentCol.LOOK_RATE)) for i in range(1, n + 1)):
        axes.append("Monitoring")
        for i in range(1, n + 1):
            per_agent[i - 1].append(
                mean_of([as_float(r.get(agent_col(i, AgentCol.LOOK_RATE))) for r in rows])
            )

    if len(axes) < 3:
        return None
    datasets = [{"label": names[i - 1], "data": per_agent[i - 1]} for i in range(1, n + 1)]
    return chart_spec(
        "behavior_radar",
        "radar",
        "Agent behaviour profile (normalised)",
        labels=axes,
        datasets=datasets,
    )


def _c_cooperation_radar(config, rows, n):
    vmap = strategy_value_map(config)
    if not vmap:
        return None
    from collections import defaultdict

    by = defaultdict(list)
    for r in rows:
        combo = [
            str(r.get(agent_col(i, AgentCol.PERSONALITY)))
            for i in range(1, n + 1)
            if not is_missing(r.get(agent_col(i, AgentCol.PERSONALITY)))
        ]
        if not combo:
            continue
        vals = []
        for i in range(1, n + 1):
            for s in as_list(r.get(agent_col(i, AgentCol.STRATEGIES))):
                v = vmap.get(str(s))
                if v is not None:
                    vals.append(1.0 if v > 0 else 0.0)
        if vals:
            by[" + ".join(combo)].append(mean_of(vals))
    labels = sorted(by)
    return chart_spec(
        "cooperation_radar",
        "radar",
        "Cooperation by personality combination",
        labels=labels,
        datasets=[{"label": "cooperation", "data": [mean_of(by[k]) for k in labels]}],
    )


def _c_top_messages(rows, n, names, top_k=8):
    from collections import Counter

    per_agent = [Counter() for _ in range(n)]
    for r in rows:
        for i in range(1, n + 1):
            for msg in as_list(r.get(agent_col(i, AgentCol.MESSAGES))):
                per_agent[i - 1][str(msg)] += 1
    totals = Counter()
    for c in per_agent:
        totals.update(c)
    labels = [m for m, _ in sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))[:top_k]]
    datasets = [
        {"label": names[i], "data": [per_agent[i].get(m, 0) for m in labels]} for i in range(n)
    ]
    return chart_spec(
        "top_messages", "bar", "Most frequent messages by agent", labels=labels, datasets=datasets
    )


def _game_welfare(r: dict[str, Any]) -> float:
    na = _count_agents([r])
    return sum(_game_total(r, i) for i in range(1, na + 1))


def _round_labels(k: int) -> list[str]:
    return [f"R{i + 1}" for i in range(k)]


def _c_score_over_rounds(rows, n, names, max_rounds):
    datasets = []
    for i in range(1, n + 1):
        data = []
        for idx in range(max_rounds):
            cums = []
            for r in rows:
                scores = [as_float(x) for x in as_list(r.get(agent_col(i, AgentCol.SCORES)))]
                if idx < len(scores):
                    cums.append(sum(v for v in scores[: idx + 1] if v is not None))
            data.append(mean_of(cums))
        datasets.append({"label": names[i - 1], "data": data})
    return chart_spec(
        "score_over_rounds",
        "line",
        "Cumulative score over rounds",
        labels=_round_labels(max_rounds),
        datasets=datasets,
    )


def _c_welfare_over_rounds(rows, max_rounds):
    data = []
    for idx in range(max_rounds):
        vals = []
        for r in rows:
            wpr = as_list(r.get("welfare_per_round"))
            if idx < len(wpr) and isinstance(wpr[idx], dict):
                vals.append(as_float(wpr[idx].get("sum")))
        data.append(mean_of(vals))
    return chart_spec(
        "welfare_over_rounds",
        "line",
        "Welfare (sum) over rounds",
        labels=_round_labels(max_rounds),
        datasets=[{"label": "welfare sum", "data": data}],
    )


def _c_belief_agreement(rows, n, names):
    data = [
        mean_of([as_float(r.get(agent_col(i, AgentCol.BELIEF_AGREEMENT_RATE))) for r in rows])
        for i in range(1, n + 1)
    ]
    return chart_spec(
        "belief_agreement",
        "bar",
        "Belief agreement rate",
        labels=names,
        datasets=[{"label": "agreement", "data": data}],
    )


def _c_equilibrium_rate(rows):
    return chart_spec(
        "equilibrium_rate",
        "bar",
        "Equilibrium play rate",
        labels=["equilibrium rate"],
        datasets=[
            {
                "label": "rate",
                "data": [mean_of([as_float(r.get("equilibrium_rate")) for r in rows])],
            }
        ],
    )


def _c_equilibrium_over_rounds(rows, max_rounds):
    data = []
    for idx in range(max_rounds):
        vals = []
        for r in rows:
            epr = as_list(r.get("equilibrium_per_round"))
            if idx < len(epr):
                vals.append(as_float(epr[idx]))
        data.append(mean_of(vals))
    return chart_spec(
        "equilibrium_over_rounds",
        "line",
        "Equilibrium reached per round",
        labels=_round_labels(max_rounds),
        datasets=[{"label": "equilibrium", "data": data}],
    )


def _c_monitoring_cost(rows, n, names):
    data = [
        mean_of([as_float(r.get(agent_col(i, AgentCol.MONITORING_COST_TOTAL))) for r in rows])
        for i in range(1, n + 1)
    ]
    return chart_spec(
        "monitoring_cost",
        "bar",
        "Monitoring cost by agent",
        labels=names,
        datasets=[{"label": "cost", "data": data}],
    )


def _grouped_mean_welfare(rows, key):
    from collections import defaultdict

    by = defaultdict(list)
    for r in rows:
        k = r.get(key)
        if not is_missing(k):
            by[str(k)].append(_game_welfare(r))
    labels = sorted(by)
    return labels, [mean_of(by[k]) for k in labels]


def _c_by_payoff_variant(rows):
    labels, data = _grouped_mean_welfare(rows, "payoff_variant_name")
    return chart_spec(
        "by_payoff_variant",
        "bar",
        "Welfare by payoff variant",
        labels=labels,
        datasets=[{"label": "mean welfare", "data": data}],
    )


def _c_by_personality(rows, n):
    from collections import defaultdict

    by = defaultdict(list)
    for r in rows:
        combo = [
            str(r.get(agent_col(i, AgentCol.PERSONALITY)))
            for i in range(1, n + 1)
            if not is_missing(r.get(agent_col(i, AgentCol.PERSONALITY)))
        ]
        if combo:
            by[" + ".join(combo)].append(_game_welfare(r))
    labels = sorted(by)
    return chart_spec(
        "by_personality",
        "bar",
        "Welfare by personality combination",
        labels=labels,
        datasets=[{"label": "mean welfare", "data": [mean_of(by[k]) for k in labels]}],
    )


def _c_seed_variability(rows):
    labels, data = _grouped_mean_welfare(rows, "seed")
    return chart_spec(
        "seed_variability",
        "bar",
        "Welfare across seeds",
        labels=labels,
        datasets=[{"label": "mean welfare", "data": data}],
    )


def _c_standings(rows, n):
    from collections import defaultdict

    totals = defaultdict(list)
    for r in rows:
        for i in range(1, n + 1):
            nm = r.get(agent_col(i, AgentCol.NAME))
            if not is_missing(nm):
                totals[str(nm)].append(_game_total(r, i))
    ranked = sorted(((nm, mean_of(v)) for nm, v in totals.items()), key=lambda kv: -kv[1])
    return chart_spec(
        "standings",
        "bar",
        "Tournament standings",
        labels=[nm for nm, _ in ranked],
        datasets=[{"label": "mean score", "data": [v for _, v in ranked]}],
    )


def build_dashboard(config: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    config = config or {}
    rows = rows or []
    if not rows:
        return {"sections": []}
    ctx = derive_context(config, rows)
    n = ctx.n_agents
    names = _agent_names(rows, n)

    # (section title, [charts]) — each section is emitted only if it has charts.
    plan: list[tuple] = []

    overview = [_c_outcome_mix(rows, n), _c_score_by_agent(rows, n, names), _c_welfare(rows)]
    radar = _c_behavior_radar(config, rows, n, names)
    if radar:
        overview.append(radar)
    plan.append(("Overview", overview))

    if ctx.is_repeated:
        coop_trend = _c_cooperation_trend(config, rows, n, names, ctx.max_rounds)
        dyn = ([coop_trend] if coop_trend else []) + [
            _c_score_over_rounds(rows, n, names, ctx.max_rounds),
            _c_welfare_over_rounds(rows, ctx.max_rounds),
        ]
        plan.append(("Dynamics", dyn))

    if ctx.has_beliefs:
        plan.append(
            (
                "Beliefs & Theory of Mind",
                [
                    _c_belief_brier(rows, n, names),
                    _c_belief_agreement(rows, n, names),
                ],
            )
        )

    if ctx.has_equilibrium:
        eq = [_c_equilibrium_rate(rows)]
        if ctx.is_repeated:
            eq.append(_c_equilibrium_over_rounds(rows, ctx.max_rounds))
        plan.append(("Equilibrium", eq))

    if ctx.has_communication:
        plan.append(
            (
                "Communication",
                [
                    _c_message_volume(rows, n, names),
                    _c_top_messages(rows, n, names),
                ],
            )
        )

    if ctx.has_trust:
        plan.append(
            (
                "Trust & Monitoring",
                [
                    _c_look_rate(rows, n, names),
                    _c_monitoring_cost(rows, n, names),
                ],
            )
        )

    if ctx.n_languages > 1:
        plan.append(
            (
                "Language",
                [
                    _c_by_language(rows),
                ],
            )
        )

    if ctx.payoff_variants:
        plan.append(
            (
                "Payoff variants",
                [
                    _c_by_payoff_variant(rows),
                ],
            )
        )

    if ctx.n_personality_combos > 1:
        pers = [_c_by_personality(rows, n)]
        if ctx.n_personality_combos >= 3:
            cr = _c_cooperation_radar(config, rows, n)
            if cr:
                pers.append(cr)
        plan.append(("Personality", pers))

    if ctx.n_seeds > 1:
        plan.append(
            (
                "Multi-seed",
                [
                    _c_seed_variability(rows),
                ],
            )
        )

    topo: list[dict[str, Any]] = []
    if ctx.has_interaction:
        topo.append(_interaction_graph(config))
    if ctx.is_tournament:
        topo.append(_c_standings(rows, n))
    if topo:
        plan.append(("Topology", topo))

    sections = [{"title": t, "charts": c} for t, c in plan if c]
    return {"sections": sections}
