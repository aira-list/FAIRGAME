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
    has_regret: bool = False
    has_equilibrium: bool = False
    has_communication: bool = False
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

    # Personality combos are counted on canonical labels: localized
    # personalities ("cooperative"/"coopératif") are the same treatment.
    pmap = canonical_personality_map(config)
    combos = set()
    for r in rows:
        combo = tuple(
            canon(pmap, r.get("language"), r.get(agent_col(i, AgentCol.PERSONALITY)))
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
        has_regret=any_agent(AgentCol.REGRET_MEAN),
        has_equilibrium=column_present(rows, "equilibrium_rate"),
        has_communication=bool(has_comm),
        n_seeds=len(seeds) or 1,
        payoff_variants=variants,
        n_personality_combos=len(combos),
    )


def chart_spec(cid: str, kind: str, title: str, **extra: Any) -> dict[str, Any]:
    ch = {"id": cid, "kind": kind, "title": title, "labels": [], "datasets": []}
    ch.update(extra)
    return ch


def worth_plotting(chart: dict[str, Any] | None) -> bool:
    """Only charts that can actually inform survive.

    Dropped: bar charts with fewer than two categories (a number, not a
    plot); charts with no numeric data; charts whose every value is
    identical (flat bars / flat lines say nothing the table doesn't); radars
    where every agent's polygon coincides (nothing to compare).
    """
    if not chart:
        return False
    datasets = chart.get("datasets") or []
    values = [v for ds in datasets for v in (ds.get("data") or []) if isinstance(v, (int, float))]
    if not values:
        return False
    if chart.get("kind") == "bar" and len(chart.get("labels") or []) < 2:
        return False
    # Flatness kills comparison charts (equal bars compare nothing) but NOT
    # count distributions (``flat_ok`` — an even outcome split is a finding).
    if not chart.get("flat_ok") and len(values) >= 2 and max(values) - min(values) < 1e-9:
        return False
    if chart.get("kind") == "radar" and len(datasets) >= 2:
        signatures = {
            tuple(
                round(v, 6) if isinstance(v, (int, float)) else None for v in ds.get("data") or []
            )
            for ds in datasets
        }
        if len(signatures) == 1:
            return False
    return True


def assemble_sections(plan: list[tuple]) -> list[dict[str, Any]]:
    """Filter trivial charts out of the plan and drop emptied sections."""
    sections = []
    for title, charts in plan:
        kept = [c for c in charts if worth_plotting(c)]
        for c in kept:
            c.pop("flat_ok", None)  # filter-internal flag, not client contract
        if kept:
            sections.append({"title": title, "charts": kept})
    return sections


def as_float(v: Any):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def mean_or_none(xs: list[Any]) -> float | None:
    """Mean of the present values, or ``None`` when nothing was recorded.

    Use this wherever a missing metric must NOT render as a confident zero
    (``mean_of``'s 0.0 fallback fabricates data on charts).
    """
    vals = [x for x in xs if x is not None]
    return round(sum(vals) / len(vals), 6) if vals else None


def mean_of(xs: list[Any]) -> float:
    v = mean_or_none(xs)
    return v if v is not None else 0.0


def canon(maps: dict[str, dict[str, str]], lang: Any, value: Any) -> str:
    """Canonical form of a localized label.

    Prefers the mapping of the row's own language — the same surface string
    can play different roles in two languages, so a flattened lookup could
    return the wrong canonical form. Falls back to the other languages' maps
    (then identity) for rows whose language is missing from the config.
    """
    s = str(value)
    m = maps.get(str(lang))
    if m and s in m:
        return m[s]
    for m2 in maps.values():
        if s in m2:
            return m2[s]
    return s


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


def _c_outcome_mix(config, rows, n):
    from collections import Counter

    smap = canonical_strategy_map(config)
    vmap = strategy_value_map(config)
    cnt: Counter = Counter()
    for r in rows:
        strat = [as_list(r.get(agent_col(i, AgentCol.STRATEGIES))) for i in range(1, n + 1)]
        for idx in range(max((len(s) for s in strat), default=0)):
            # Localized labels mean the same move — aggregate on the
            # canonical-language label so EN/FR/… rows count together.
            combo = [canon(smap, r.get("language"), s[idx]) for s in strat if idx < len(s)]
            if len(combo) == n:
                cnt[_combo_label(combo, vmap)] += 1
    items = sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))
    return chart_spec(
        "outcome_mix",
        "bar",
        "Outcome mix",
        flat_ok=True,
        description=(
            "How often each joint outcome occurred, over all games and rounds. Labels are unified "
            "across languages; the suffix gives the game-theoretic reading."
        ),
        labels=[k for k, _ in items],
        datasets=[{"label": "games × rounds", "data": [v for _, v in items]}],
    )


def _c_score_by_agent(rows, n, names):
    data = [mean_of([_game_total(r, i) for r in rows]) for i in range(1, n + 1)]
    return chart_spec(
        "score_by_agent",
        "bar",
        "Mean score by agent",
        description="Average total score per game for each agent — higher is better.",
        labels=names,
        datasets=[{"label": "mean total score", "data": data}],
    )


def _c_welfare(rows):
    # Only metrics that were actually recorded, and only ratio-scale ones
    # (0..1) so the bars share an axis. A missing metric is OMITTED — never
    # painted as a fabricated zero. Raw-scale figures (min score, welfare
    # sum) live in the DataFrame view.
    candidates = [
        ("Efficiency", "welfare_efficiency"),
        ("Inequality (Gini)", "welfare_mean_gini"),
    ]
    labels, data = [], []
    for label, col in candidates:
        v = mean_or_none([as_float(r.get(col)) for r in rows])
        if v is not None:
            labels.append(label)
            data.append(v)
    return chart_spec(
        "welfare",
        "bar",
        "Welfare",
        description=(
            "Group outcome quality on 0-1 scales, averaged over games: efficiency of the total "
            "payoff and inequality (Gini, 0 = perfectly equal)."
        ),
        labels=labels,
        datasets=[{"label": "mean", "data": data}],
    )


def _c_belief_brier(rows, n, names):
    data = [
        mean_or_none([as_float(r.get(agent_col(i, AgentCol.BELIEF_MEAN_BRIER))) for r in rows])
        for i in range(1, n + 1)
    ]
    return chart_spec(
        "belief_brier",
        "bar",
        "Belief accuracy (Brier — lower is better)",
        description=(
            "Brier score of each agent's predictions of the opponent's move: 0 = perfect foresight, "
            "lower is better."
        ),
        labels=names,
        datasets=[{"label": "mean Brier", "data": data}],
    )


def _row_languages(rows) -> list[str]:
    return sorted({r.get("language") for r in rows if not is_missing(r.get("language"))})


def _c_by_language(rows):
    from collections import defaultdict

    langs = _row_languages(rows)
    by = defaultdict(list)
    for r in rows:
        na = _count_agents([r])
        by[r.get("language")].append(sum(_game_total(r, i) for i in range(1, na + 1)))
    return chart_spec(
        "by_language",
        "bar",
        "Welfare by language",
        # Equal bars = no language bias — for a bias study that IS the
        # result, so this chart is exempt from the flatness gate.
        flat_ok=True,
        description=(
            "Mean welfare (sum of scores) per prompt language — systematic differences suggest "
            "language bias; equal bars mean none was observed."
        ),
        labels=langs,
        datasets=[{"label": "mean welfare", "data": [mean_of(by[lang]) for lang in langs]}],
    )


def _c_cooperation_by_language(config, rows, n):
    vmap = strategy_value_map(config)
    if not vmap:
        return None
    from collections import defaultdict

    langs = _row_languages(rows)
    by: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        for i in range(1, n + 1):
            for s in as_list(r.get(agent_col(i, AgentCol.STRATEGIES))):
                v = vmap.get(str(s))
                if v is not None:
                    by[r.get("language")].append(1.0 if v > 0 else 0.0)
    return chart_spec(
        "coop_by_language",
        "bar",
        "Cooperation by language",
        flat_ok=True,
        description=(
            "Share of cooperative (first-option) choices per prompt language — the study's "
            "headline language-bias signal. Equal bars mean the language did not change behaviour."
        ),
        labels=langs,
        datasets=[{"label": "cooperation share", "data": [mean_of(by[lang]) for lang in langs]}],
    )


def _c_outcomes_by_language(config, rows, n):
    """Joint-outcome counts per language (languages on the x-axis, one
    series per canonical outcome), so convergence or divergence across
    languages is visible even when every game ends the same way."""
    from collections import Counter, defaultdict

    smap = canonical_strategy_map(config)
    vmap = strategy_value_map(config)
    langs = _row_languages(rows)
    counts: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        strat = [as_list(r.get(agent_col(i, AgentCol.STRATEGIES))) for i in range(1, n + 1)]
        for idx in range(max((len(s) for s in strat), default=0)):
            combo = [canon(smap, r.get("language"), s[idx]) for s in strat if idx < len(s)]
            if len(combo) == n:
                counts[r.get("language")][_combo_label(combo, vmap)] += 1
    categories = sorted({cat for c in counts.values() for cat in c})
    return chart_spec(
        "outcomes_by_language",
        "bar",
        "Outcomes by language",
        flat_ok=True,
        description=(
            "How often each joint outcome occurred in every prompt language (labels unified "
            "across languages) — shows whether the languages converge on the same behaviour."
        ),
        labels=langs,
        datasets=[
            {"label": cat, "data": [counts[lang].get(cat, 0) for lang in langs]}
            for cat in categories
        ],
    )


def _c_look_rate(rows, n, names):
    data = [
        mean_or_none([as_float(r.get(agent_col(i, AgentCol.LOOK_RATE))) for r in rows])
        for i in range(1, n + 1)
    ]
    return chart_spec(
        "look_rate",
        "bar",
        "Monitoring (LOOK) rate by agent",
        description=(
            "Share of rounds each agent paid the monitoring cost to observe its opponent's history "
            "(LOOK) instead of acting blind."
        ),
        labels=names,
        datasets=[{"label": "LOOK rate", "data": data}],
    )


def _strategy_role_labels(config: dict[str, Any]):
    """Yield ``(role, label)`` across every language map in
    ``payoffMatrix.strategies`` — the one walker of that config shape."""
    strat = (config.get("payoffMatrix") or {}).get("strategies") or {}
    for d in strat.values():
        if not isinstance(d, dict):
            continue
        for role in ("strategy1", "strategy2"):
            if d.get(role) is not None:
                yield role, str(d[role])


def strategy_value_map(config: dict[str, Any]) -> dict[str, float]:
    """Map each strategy display label to the paper's signed value:
    strategy1 (Option A / cooperate) = +1, strategy2 = -1."""
    return {
        label: (1.0 if role == "strategy1" else -1.0)
        for role, label in _strategy_role_labels(config)
    }


def _canonical_language(keys: list[str]) -> str | None:
    """The reference language for display labels: English when present."""
    if not keys:
        return None
    return "en" if "en" in keys else keys[0]


def canonical_strategy_map(config: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Per-language map: localized strategy label -> canonical-language label.

    Strategy labels are configured per language but play the same role
    (``strategy1`` / ``strategy2``), so charts must aggregate e.g. FR
    "Coopérer" together with EN "OptionA" rather than as separate bars.
    Keyed by language so a label that plays different roles in two languages
    cannot shadow the right entry (see :func:`canon`).
    """
    strat = (config.get("payoffMatrix") or {}).get("strategies") or {}
    canon_lang = _canonical_language([k for k, v in strat.items() if isinstance(v, dict)])
    if canon_lang is None:
        return {}
    canonical = strat[canon_lang]
    return {
        str(lang): {
            str(d[role]): str(canonical[role])
            for role in ("strategy1", "strategy2")
            if d.get(role) is not None and canonical.get(role) is not None
        }
        for lang, d in strat.items()
        if isinstance(d, dict)
    }


def canonical_personality_map(config: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Per-language map: localized personality -> canonical-language personality.

    ``agents.personalities`` holds one parallel list per language (same
    position = same personality translated), so map positionally — scoped by
    language so false friends at different positions cannot collide.
    """
    pers = (config.get("agents") or {}).get("personalities") or {}
    canon_lang = _canonical_language([k for k, v in pers.items() if isinstance(v, list)])
    if canon_lang is None:
        return {}
    canon_list = pers[canon_lang]
    return {
        str(lang): {str(p): str(canon_list[i]) for i, p in enumerate(lst) if i < len(canon_list)}
        for lang, lst in pers.items()
        if isinstance(lst, list)
    }


def _combo_label(combo: list[str], vmap: dict[str, float] | None = None) -> str:
    """Readable label for a joint play: "Both X" / "All X" when uniform,
    otherwise the per-agent labels ("X + Y").

    When the game's ±1 strategy mapping covers the combo, the outcome's
    game-theoretic reading is appended (strategy1 = the cooperative pole —
    the same convention as the cooperation trend / radar), so opaque labels
    like "Both OptionB" still say what happened: "mutual defection".
    """
    if len(combo) >= 2 and len(set(combo)) == 1:
        base = ("Both " if len(combo) == 2 else "All ") + combo[0]
    else:
        base = " + ".join(combo)
    if vmap and all(label in vmap for label in combo):
        vals = {vmap[label] for label in combo}
        if vals == {1.0}:
            base += " — mutual cooperation" if len(combo) == 2 else " — all cooperate"
        elif vals == {-1.0}:
            base += " — mutual defection" if len(combo) == 2 else " — all defect"
        else:
            base += " — mixed"
    return base


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
        description=(
            "Average played strategy per round: +1 = everyone chose the first (cooperative) option, "
            "-1 = the second."
        ),
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
                mean_or_none([as_float(r.get(agent_col(i, AgentCol.LOOK_RATE))) for r in rows])
            )
    if any(column_present(rows, agent_col(i, AgentCol.REGRET_MEAN)) for i in range(1, n + 1)):
        # Inverted + normalised (1 = the least-regretful agent in this run),
        # so the axis reads "bigger is better" like every other radar axis.
        axes.append("Low regret")
        regrets = [
            mean_or_none([as_float(r.get(agent_col(i, AgentCol.REGRET_MEAN))) for r in rows])
            for i in range(1, n + 1)
        ]
        # Min-max scaled so the semantics match the axis name: 1 = the
        # least-regretful agent in this run, 0 = the most. When every agent
        # has equal regret there is no contrast — all are jointly the least
        # regretful, so all score 1.
        present = [v for v in regrets if v is not None]
        mn = min(present, default=0.0)
        span = (max(present, default=0.0) - mn) or 0.0
        for i in range(1, n + 1):
            v = regrets[i - 1]
            per_agent[i - 1].append(
                None if v is None else round(1.0 - ((v - mn) / span if span else 0.0), 6)
            )

    if len(axes) < 3:
        return None
    datasets = [{"label": names[i - 1], "data": per_agent[i - 1]} for i in range(1, n + 1)]
    return chart_spec(
        "behavior_radar",
        "radar",
        "Agent behaviour profile (normalised)",
        description=(
            "Behavioural fingerprint per agent, each axis normalised to 0-1 (rim = best observed): "
            "cooperation share, relative score, and where recorded belief accuracy, monitoring and "
            "low regret."
        ),
        labels=axes,
        datasets=datasets,
    )


def _c_cooperation_radar(config, rows, n):
    vmap = strategy_value_map(config)
    if not vmap:
        return None
    from collections import defaultdict

    pmap = canonical_personality_map(config)
    by = defaultdict(list)
    for r in rows:
        combo = [
            canon(pmap, r.get("language"), r.get(agent_col(i, AgentCol.PERSONALITY)))
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
        description="Cooperation share for each personality pairing — rim = always the cooperative option.",
        labels=labels,
        datasets=[{"label": "cooperation", "data": [mean_of(by[k]) for k in labels]}],
    )


def _is_covert(config) -> bool:
    """True when the communication channel carries decoy sequences
    (``fakeCommunication`` — a boolean per the configuration schema)."""
    return truthy((config or {}).get("fakeCommunication"))


def _c_top_messages(config, rows, n, names, top_k=8):
    from collections import Counter

    # Covert channels exchange random decoy sequences — a frequency chart
    # of noise is meaningless (and the hex labels are unreadable).
    if _is_covert(config):
        return None
    # Messages that ARE a strategy label (agents often just announce their
    # move) fold onto the canonical-language label, so "OpzioneB" and
    # "OptionB" count as the same announcement. Free text stays untouched.
    smap = canonical_strategy_map(config)
    per_agent = [Counter() for _ in range(n)]
    for r in rows:
        for i in range(1, n + 1):
            for msg in as_list(r.get(agent_col(i, AgentCol.MESSAGES))):
                per_agent[i - 1][canon(smap, r.get("language"), msg)] += 1
    totals = Counter()
    for c in per_agent:
        totals.update(c)
    # Free-text messages that all occur once are an arbitrary sample, not a
    # "most frequent" ranking — only chart when something actually repeats.
    if not totals or max(totals.values()) < 2:
        return None
    full = [m for m, _ in sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))[:top_k]]
    labels = [(m[:45] + "…") if len(m) > 46 else m for m in full]
    datasets = [
        {"label": names[i], "data": [per_agent[i].get(m, 0) for m in full]} for i in range(n)
    ]
    return chart_spec(
        "top_messages",
        "bar",
        "Most frequent messages by agent",
        flat_ok=True,
        description="Messages that were sent more than once, split by sender.",
        labels=labels,
        datasets=datasets,
    )


def _game_welfare(r: dict[str, Any]) -> float:
    na = _count_agents([r])
    return sum(_game_total(r, i) for i in range(1, na + 1))


def _round_labels(k: int) -> list[str]:
    return [f"R{i + 1}" for i in range(k)]


def _c_agent_field_over_rounds(
    cid, title, rows, n, names, max_rounds, list_field, value_fn, description=""
):
    """Line chart of a per-round agent list field, averaged across games.

    Rounds where an agent has no data become ``None`` (a gap in the line)
    rather than a fake zero. ``value_fn`` maps a raw list entry to a float
    or ``None``.
    """
    datasets = []
    for i in range(1, n + 1):
        per_round: list[list[float]] = [[] for _ in range(max_rounds)]
        for r in rows:  # parse each row's list once, not once per round
            lst = as_list(r.get(agent_col(i, list_field)))
            for idx in range(min(len(lst), max_rounds)):
                v = value_fn(lst[idx])
                if v is not None:
                    per_round[idx].append(v)
        data = [mean_or_none(vals) for vals in per_round]
        datasets.append({"label": names[i - 1], "data": data})
    return chart_spec(
        cid,
        "line",
        title,
        description=description,
        labels=_round_labels(max_rounds),
        datasets=datasets,
    )


def _look_value(v: Any):
    if isinstance(v, str):
        s = v.strip().upper()
        if s == "LOOK":
            return 1.0
        if s == "NO_LOOK":
            return 0.0
    return None


def _c_regret_by_agent(rows, n, names):
    data = [
        mean_or_none([as_float(r.get(agent_col(i, AgentCol.REGRET_MEAN))) for r in rows])
        for i in range(1, n + 1)
    ]
    return chart_spec(
        "regret_by_agent",
        "bar",
        "Mean regret by agent (lower is better)",
        description=(
            "Average gap between what an agent scored and the best it could have scored against the "
            "opponents' actual moves — 0 means it always best-responded."
        ),
        labels=names,
        datasets=[{"label": "mean regret", "data": data}],
    )


def _c_score_over_rounds(rows, n, names, max_rounds):
    # Per-round mean (NOT cumulative): cumulating near-constant payoffs
    # renders as a straight line that hides exactly the deviations this
    # chart exists to show.
    datasets = []
    for i in range(1, n + 1):
        data = []
        for idx in range(max_rounds):
            vals = []
            for r in rows:
                scores = [as_float(x) for x in as_list(r.get(agent_col(i, AgentCol.SCORES)))]
                if idx < len(scores) and scores[idx] is not None:
                    vals.append(scores[idx])
            data.append(mean_or_none(vals))
        datasets.append({"label": names[i - 1], "data": data})
    return chart_spec(
        "score_over_rounds",
        "line",
        "Score per round",
        description=(
            "Each agent's payoff in every round, averaged over games — dips and jumps show "
            "retaliation, exploitation, or coordination shifts."
        ),
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
        description="Total payoff earned by all agents in each round, averaged over games.",
        labels=_round_labels(max_rounds),
        datasets=[{"label": "welfare sum", "data": data}],
    )


def _c_belief_agreement(rows, n, names):
    data = [
        mean_or_none([as_float(r.get(agent_col(i, AgentCol.BELIEF_AGREEMENT_RATE))) for r in rows])
        for i in range(1, n + 1)
    ]
    return chart_spec(
        "belief_agreement",
        "bar",
        "Belief agreement rate",
        description=(
            "Fraction of rounds where the agent's most-likely predicted move matched what the "
            "opponent actually played."
        ),
        labels=names,
        datasets=[{"label": "agreement", "data": data}],
    )


def _c_equilibrium_rate(rows):
    # Two complementary shares rather than a single-value bar: a lone label
    # is (rightly) dropped by worth_plotting, which used to erase the whole
    # Equilibrium section for one-shot runs. ``flat_ok`` because an exact
    # 50/50 split is a finding, not a flat non-chart.
    rate = mean_of([as_float(r.get("equilibrium_rate")) for r in rows])
    return chart_spec(
        "equilibrium_rate",
        "bar",
        "Equilibrium play rate",
        description="Share of all rounds where the joint play was a Nash equilibrium of the stage game.",
        labels=["at equilibrium", "off equilibrium"],
        datasets=[{"label": "share of rounds", "data": [rate, round(1 - rate, 6)]}],
        flat_ok=True,
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
        description="Share of games whose play was in equilibrium at each round.",
        labels=_round_labels(max_rounds),
        datasets=[{"label": "equilibrium", "data": data}],
    )


def _c_monitoring_cost(rows, n, names):
    data = [
        mean_or_none([as_float(r.get(agent_col(i, AgentCol.MONITORING_COST_TOTAL))) for r in rows])
        for i in range(1, n + 1)
    ]
    return chart_spec(
        "monitoring_cost",
        "bar",
        "Monitoring cost by agent",
        description="Average total score each agent spent on monitoring per game.",
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
        description="Mean welfare under each payoff-matrix variant of this configuration group.",
        labels=labels,
        datasets=[{"label": "mean welfare", "data": data}],
    )


def _c_by_personality(config, rows, n):
    from collections import defaultdict

    pmap = canonical_personality_map(config)
    by = defaultdict(list)
    for r in rows:
        combo = [
            canon(pmap, r.get("language"), r.get(agent_col(i, AgentCol.PERSONALITY)))
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
        description="Mean welfare for each personality pairing (labels unified across languages).",
        labels=labels,
        datasets=[{"label": "mean welfare", "data": [mean_of(by[k]) for k in labels]}],
    )


def _c_seed_variability(rows):
    labels, data = _grouped_mean_welfare(rows, "seed")
    return chart_spec(
        "seed_variability",
        "bar",
        "Welfare across seeds",
        description="Mean welfare per random seed — a wide spread means results are seed-sensitive.",
        labels=labels,
        datasets=[{"label": "mean welfare", "data": data}],
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

    overview = [
        _c_outcome_mix(config, rows, n),
        _c_score_by_agent(rows, n, names),
        _c_welfare(rows),
    ]
    if ctx.has_regret:
        overview.append(_c_regret_by_agent(rows, n, names))
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
        if ctx.has_regret:
            dyn.append(
                _c_agent_field_over_rounds(
                    "regret_over_rounds",
                    "Regret per round (lower is better)",
                    rows,
                    n,
                    names,
                    ctx.max_rounds,
                    AgentCol.REGRET_PER_ROUND,
                    as_float,
                    description=(
                        "Average regret in each round — a falling line means the "
                        "agents converge on best responses."
                    ),
                )
            )
        plan.append(("Dynamics", dyn))

    if ctx.has_beliefs:
        beliefs = [
            _c_belief_brier(rows, n, names),
            _c_belief_agreement(rows, n, names),
        ]
        if ctx.is_repeated:
            beliefs.append(
                _c_agent_field_over_rounds(
                    "brier_over_rounds",
                    "Belief accuracy over rounds (Brier — lower is better)",
                    rows,
                    n,
                    names,
                    ctx.max_rounds,
                    AgentCol.BELIEF_BRIER_PER_ROUND,
                    as_float,
                    description=(
                        "Prediction error per round — a falling line means the "
                        "agent is learning its opponent."
                    ),
                )
            )
        plan.append(("Beliefs & Theory of Mind", beliefs))

    if ctx.has_equilibrium:
        eq = [_c_equilibrium_rate(rows)]
        if ctx.is_repeated:
            eq.append(_c_equilibrium_over_rounds(rows, ctx.max_rounds))
        plan.append(("Equilibrium", eq))

    if ctx.has_communication:
        plan.append(("Communication", [_c_top_messages(config, rows, n, names)]))

    if ctx.has_trust:
        trust = [
            _c_look_rate(rows, n, names),
            _c_monitoring_cost(rows, n, names),
        ]
        if ctx.is_repeated:
            trust.append(
                _c_agent_field_over_rounds(
                    "look_over_rounds",
                    "Monitoring (LOOK) rate over rounds",
                    rows,
                    n,
                    names,
                    ctx.max_rounds,
                    AgentCol.TRUST_ACTIONS,
                    _look_value,
                    description=(
                        "Monitoring rate per round — shows when agents stop "
                        "(or start) paying for information."
                    ),
                )
            )
        plan.append(("Trust & Monitoring", trust))

    if ctx.n_languages > 1:
        plan.append(
            (
                "Language",
                [
                    _c_cooperation_by_language(config, rows, n),
                    _c_by_language(rows),
                    _c_outcomes_by_language(config, rows, n),
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
        pers = [_c_by_personality(config, rows, n)]
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

    return {"sections": assemble_sections(plan)}
