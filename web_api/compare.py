"""Adaptive cross-run Compare view.

Given any set of runs, derive what varies across the selection (models,
scenarios, languages, payoff types, rounds), pick a primary grouping
dimension, and emit only the charts whose data is available across the whole
selection. Never breaks on heterogeneous selections — a chart (or a
robustness-radar axis) is included only when it is computable.

Robustness dimensions (per group), from the FAIRGAME paper:
* I_V — internal variability: variance of final total payoff.
* C_I — cross-language inconsistency: std across languages of mean final payoff.
* S_P — sensitivity to payoff: std across payoff types of mean final payoff.
* V_R — variability over rounds: mean variance of the signed strategy trajectory.

Emits the same chart-spec schema as :mod:`web_api.dashboards`.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from src.results_processing.row_schema import AgentCol, agent_col
from web_api.dashboards import (
    as_float,
    as_list,
    assemble_sections,
    chart_spec,
    is_missing,
    mean_of,
    strategy_value_map,
)

# Runs named by the "<scenario> [<provider>]" convention group under the bare
# scenario. Any bracketed suffix counts — a hardcoded provider list would
# silently split the grouping the day a new provider name appears.
_PROVIDER_SUFFIX_RE = re.compile(r"\s+\[[^\[\]]+\]$")


def _scenario(config: dict[str, Any]) -> str:
    name = str((config or {}).get("name") or "scenario")
    return _PROVIDER_SUFFIX_RE.sub("", name)


def _variance(xs: list[float]) -> float:
    vals = [x for x in xs if x is not None]
    if not vals:
        return 0.0
    m = sum(vals) / len(vals)
    return round(sum((x - m) ** 2 for x in vals) / len(vals), 6)


def _std(xs: list[float]) -> float:
    return round(math.sqrt(_variance(xs)), 6)


def _observations(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One observation per game row: model + tags + final payoff + signed trajectory."""
    obs: list[dict[str, Any]] = []
    for run in runs or []:
        config = run.get("config") or {}
        vmap = strategy_value_map(config)
        scenario = _scenario(config)
        for r in run.get("rows") or []:
            model = r.get(agent_col(1, AgentCol.LLM))
            if is_missing(model):
                continue
            # agent{i}_scores hold one payoff per round — the final total
            # payoff is their sum, not the last round's entry.
            a1 = [as_float(x) for x in as_list(r.get(agent_col(1, AgentCol.SCORES)))]
            a2 = [as_float(x) for x in as_list(r.get(agent_col(2, AgentCol.SCORES)))]
            final_sum = sum(x for x in a1 + a2 if x is not None)
            s1 = [
                vmap[str(s)]
                for s in as_list(r.get(agent_col(1, AgentCol.STRATEGIES)))
                if str(s) in vmap
            ]
            s2 = [
                vmap[str(s)]
                for s in as_list(r.get(agent_col(2, AgentCol.STRATEGIES)))
                if str(s) in vmap
            ]
            k = min(len(s1), len(s2))
            traj = [(s1[i] + s2[i]) / 2 for i in range(k)]
            coop = [1.0 if v > 0 else 0.0 for v in (s1 + s2)]
            try:
                rounds = int(r.get("played_rounds") or 1)
            except (TypeError, ValueError):
                rounds = 1
            obs.append(
                {
                    "model": str(model),
                    "scenario": scenario,
                    "language": None if is_missing(r.get("language")) else str(r.get("language")),
                    "payoff_type": None
                    if is_missing(r.get("payoff_variant_name"))
                    else str(r.get("payoff_variant_name")),
                    "rounds": rounds,
                    "final_sum": final_sum,
                    "traj": traj,
                    "coop": coop,
                    "has_vmap": bool(vmap),
                }
            )
    return obs


@dataclass
class CompareContext:
    models: list[str] = field(default_factory=list)
    scenarios: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    payoff_types: list[str] = field(default_factory=list)
    all_repeated: bool = False
    any_repeated: bool = False
    primary: str = "model"
    axes: list[str] = field(default_factory=list)


def derive_compare_context(runs: list[dict[str, Any]]) -> CompareContext:
    obs = _observations(runs)
    models = sorted({o["model"] for o in obs})
    scenarios = sorted({o["scenario"] for o in obs})
    languages = sorted({o["language"] for o in obs if o["language"]})
    payoff_types = sorted({o["payoff_type"] for o in obs if o["payoff_type"]})
    rounds = [o["rounds"] for o in obs]
    all_repeated = bool(obs) and all(rr > 1 for rr in rounds)
    any_repeated = any(rr > 1 for rr in rounds)

    if len(models) > 1:
        primary = "model"
    elif len(scenarios) > 1:
        primary = "scenario"
    elif len(languages) > 1:
        primary = "language"
    else:
        primary = "model"

    # Robustness-radar axes: only those the selection can actually populate.
    axes = ["I_V"] if obs else []
    if len(languages) > 1:
        axes.append("C_I")
    if len(payoff_types) > 1:
        axes.append("S_P")
    if any_repeated:
        axes.append("V_R")

    return CompareContext(
        models=models,
        scenarios=scenarios,
        languages=languages,
        payoff_types=payoff_types,
        all_repeated=all_repeated,
        any_repeated=any_repeated,
        primary=primary,
        axes=axes,
    )


def compute_group_stats(runs: list[dict[str, Any]], by: str) -> dict[str, dict[str, Any]]:
    obs = _observations(runs)
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for o in obs:
        # An observation without the grouping tag (e.g. a language-less row
        # when grouping by language) can't be attributed to any group — and a
        # ``None`` key would blow up the ``sorted(stats)`` downstream.
        if o[by] is None:
            continue
        groups[o[by]].append(o)

    stats: dict[str, dict[str, Any]] = {}
    for g, items in groups.items():
        finals = [o["final_sum"] for o in items]
        coop = [c for o in items for c in o["coop"]]
        by_lang = defaultdict(list)
        by_type = defaultdict(list)
        for o in items:
            if o["language"]:
                by_lang[o["language"]].append(o["final_sum"])
            if o["payoff_type"]:
                by_type[o["payoff_type"]].append(o["final_sum"])
        lang_means = [mean_of(v) for v in by_lang.values()]
        type_means = [mean_of(v) for v in by_type.values()]
        round_vars = [_variance(o["traj"]) for o in items if len(o["traj"]) >= 2]
        # per-round mean trajectory
        max_r = max((len(o["traj"]) for o in items), default=0)
        trend = []
        for idx in range(max_r):
            vals = [o["traj"][idx] for o in items if idx < len(o["traj"])]
            trend.append(mean_of(vals))
        stats[g] = {
            "payoff": mean_of(finals),
            "cooperation": mean_of(coop),
            "i_v": _variance(finals),
            "c_i": _std(lang_means) if len(lang_means) > 1 else 0.0,
            "s_p": _std(type_means) if len(type_means) > 1 else 0.0,
            "v_r": mean_of(round_vars),
            "by_lang": {lang: mean_of(v) for lang, v in by_lang.items()},
            "trend": trend,
        }
    return stats


def _normalise(values: list[float]) -> list[float]:
    mx = max(values) if values else 0
    return [round(v / mx, 6) if mx else 0.0 for v in values]


_AXIS_KEY = {"I_V": "i_v", "C_I": "c_i", "S_P": "s_p", "V_R": "v_r"}


def build_comparison(runs: list[dict[str, Any]]) -> dict[str, Any]:
    ctx = derive_compare_context(runs)
    if not ctx.models:
        return {"sections": []}
    stats = compute_group_stats(runs, ctx.primary)
    groups = sorted(stats)

    label = {"model": "model", "scenario": "game", "language": "language"}[ctx.primary]
    overview = [
        chart_spec(
            "compare_cooperation",
            "bar",
            f"Cooperation by {label}",
            flat_ok=True,
            description="Share of cooperative (first-option) choices in each group, across all selected runs.",
            labels=groups,
            datasets=[{"label": "cooperation", "data": [stats[g]["cooperation"] for g in groups]}],
        ),
        chart_spec(
            "compare_payoff",
            "bar",
            f"Mean final payoff by {label}",
            flat_ok=True,
            description="Average total payoff per game in each group.",
            labels=groups,
            datasets=[{"label": "final payoff", "data": [stats[g]["payoff"] for g in groups]}],
        ),
    ]

    # Robustness radar — only the axes the selection can populate, ≥3 for a radar.
    if len(ctx.axes) >= 3:
        norm = {ax: _normalise([stats[g][_AXIS_KEY[ax]] for g in groups]) for ax in ctx.axes}
        ds = [{"label": g, "data": [norm[ax][j] for ax in ctx.axes]} for j, g in enumerate(groups)]
        overview.append(
            chart_spec(
                "robustness_radar",
                "radar",
                f"Robustness profile by {label} (normalised — smaller is more robust)",
                description=(
                    "Stability profile: internal variance (I_V), cross-language inconsistency (C_I), "
                    "payoff-matrix sensitivity (S_P), round-to-round variability (V_R). Nearer the "
                    "centre = more robust."
                ),
                labels=list(ctx.axes),
                datasets=ds,
            )
        )

    plan: list[tuple] = [("Comparison", overview)]

    # Second dimension: games as a grouped bar when models is primary and games vary.
    if ctx.primary == "model" and len(ctx.scenarios) > 1:
        # model x scenario grid for cooperation
        obs = _observations(runs)
        grid = defaultdict(list)
        for o in obs:
            grid[(o["model"], o["scenario"])].append(o)
        ds = []
        for m in ctx.models:
            data = [
                mean_of([c for o in grid.get((m, s), []) for c in o["coop"]]) for s in ctx.scenarios
            ]
            ds.append({"label": m, "data": data})
        plan.append(
            (
                "Across games",
                [
                    chart_spec(
                        "cooperation_by_game",
                        "bar",
                        "Cooperation by game and model",
                        description=(
                            "Cooperation share of each model, split by game — reveals whether a "
                            "model's behaviour is game-specific."
                        ),
                        labels=list(ctx.scenarios),
                        datasets=ds,
                    ),
                ],
            )
        )

    # Cross-language as a SECONDARY dimension (grouped by the primary group).
    # When language IS the primary axis, compare_* already break out by language,
    # so a separate (and degenerate) per-language chart would be redundant.
    if len(ctx.languages) > 1 and ctx.primary != "language":
        ds = [
            {"label": g, "data": [stats[g]["by_lang"].get(lang, 0.0) for lang in ctx.languages]}
            for g in groups
        ]
        plan.append(
            (
                "Language",
                [
                    chart_spec(
                        "payoff_by_language",
                        "bar",
                        f"Final payoff by language and {label}",
                        description=(
                            "Average final payoff split by prompt language — differences within a "
                            "group suggest language bias."
                        ),
                        labels=list(ctx.languages),
                        datasets=ds,
                    ),
                ],
            )
        )

    # Per-round trends only when every selected run is repeated.
    if ctx.all_repeated:
        max_len = max((len(stats[g]["trend"]) for g in groups), default=0)
        if max_len > 1:
            ds = [{"label": g, "data": stats[g]["trend"]} for g in groups if stats[g]["trend"]]
            plan.append(
                (
                    "Dynamics",
                    [
                        chart_spec(
                            "strategy_trend",
                            "line",
                            f"Strategy value over rounds by {label} (+1 = Option A, -1 = Option B)",
                            description=(
                                "Average played strategy per round for each group: +1 = cooperative "
                                "option, -1 = the other."
                            ),
                            labels=[f"R{i + 1}" for i in range(max_len)],
                            datasets=ds,
                        ),
                    ],
                )
            )

    return {"sections": assemble_sections(plan)}
