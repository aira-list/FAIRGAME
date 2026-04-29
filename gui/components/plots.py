"""Plotly figures for the Results page.

Figures consume the raw results dict (``factory.create_and_run_games(...)``)
or the per-game DataFrame produced by :class:`ResultsProcessor`. Each helper
gracefully returns ``None`` when the underlying data is missing so callers
can hide the chart slot rather than display an empty axis.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


_PALETTE = px.colors.qualitative.Set2


def _layout(fig: go.Figure, title: str, height: int = 360) -> go.Figure:
    fig.update_layout(
        title=title,
        title_font_size=16,
        height=height,
        margin=dict(l=10, r=10, t=50, b=20),
        plot_bgcolor="white",
        paper_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    fig.update_xaxes(showgrid=False, showline=True, linecolor="#cbd5e1")
    fig.update_yaxes(gridcolor="#e2e8f0", zeroline=False)
    return fig


def cooperation_rate_per_round(raw: Dict[str, Any]) -> Optional[go.Figure]:
    """Per-agent fraction of "cooperate"-flavoured plays at each round.

    A move counts as cooperative if its strategy label appears as
    ``strategy1`` in the game's payoff matrix (the convention shared with
    the canonical baseline strategies).
    """
    rows: List[Dict[str, Any]] = []
    for game_id, game in raw.items():
        desc = game.get("description", {})
        history = game.get("history", {})
        matrix_summary = desc.get("payoff_matrix_summary") or {}
        strategies_per_lang = matrix_summary.get("strategies") or {}
        labels = strategies_per_lang.get(desc.get("language") or "en") or {}
        if not labels:
            continue
        cooperate_label = labels.get("strategy1")
        if not cooperate_label:
            continue
        for round_key, entries in history.items():
            try:
                round_num = int(round_key.split("_")[1])
            except (IndexError, ValueError):
                continue
            for entry in entries:
                rows.append(
                    {
                        "game_id": game_id,
                        "agent": entry["agent"],
                        "round": round_num,
                        "cooperative": int(entry.get("strategy") == cooperate_label),
                    }
                )

    if not rows:
        return None

    df = pd.DataFrame(rows)
    summary = (
        df.groupby(["agent", "round"], as_index=False)["cooperative"].mean()
        .rename(columns={"cooperative": "rate"})
    )
    fig = px.line(
        summary,
        x="round",
        y="rate",
        color="agent",
        markers=True,
        color_discrete_sequence=_PALETTE,
    )
    fig.update_yaxes(range=[-0.02, 1.02], tickformat=".0%")
    return _layout(fig, "Cooperation rate per round")


def score_per_round(raw: Dict[str, Any]) -> Optional[go.Figure]:
    rows: List[Dict[str, Any]] = []
    for game_id, game in raw.items():
        for round_key, entries in (game.get("history") or {}).items():
            try:
                round_num = int(round_key.split("_")[1])
            except (IndexError, ValueError):
                continue
            for entry in entries:
                if entry.get("score") is None:
                    continue
                rows.append(
                    {
                        "game_id": game_id,
                        "agent": entry["agent"],
                        "round": round_num,
                        "score": float(entry["score"]),
                    }
                )
    if not rows:
        return None
    df = pd.DataFrame(rows)
    summary = df.groupby(["agent", "round"], as_index=False)["score"].mean()
    fig = px.line(
        summary,
        x="round",
        y="score",
        color="agent",
        markers=True,
        color_discrete_sequence=_PALETTE,
    )
    return _layout(fig, "Mean score per round")


def welfare_breakdown(df: pd.DataFrame) -> Optional[go.Figure]:
    cols = ["welfare_mean_sum", "welfare_mean_min", "welfare_mean_gini"]
    available = [c for c in cols if c in df.columns]
    if not available:
        return None
    record: Dict[str, float] = {}
    for col in available:
        series = pd.to_numeric(df[col], errors="coerce")
        if series.notna().any():
            record[col.replace("welfare_mean_", "").title()] = float(series.mean())
    if not record:
        return None
    fig = go.Figure(go.Bar(x=list(record.keys()), y=list(record.values()), marker_color=_PALETTE))
    return _layout(fig, "Welfare summary (mean across games)")


def equilibrium_rate_bar(df: pd.DataFrame) -> Optional[go.Figure]:
    if "equilibrium_rate" not in df.columns:
        return None
    series = pd.to_numeric(df["equilibrium_rate"], errors="coerce").dropna()
    if series.empty:
        return None
    fig = go.Figure(
        go.Histogram(x=series.tolist(), nbinsx=10, marker_color=_PALETTE[2])
    )
    fig.update_xaxes(range=[0, 1])
    return _layout(fig, "Equilibrium-rate distribution across games")


def brier_per_round(raw: Dict[str, Any]) -> Optional[go.Figure]:
    rows: List[Dict[str, Any]] = []
    for game_id, game in raw.items():
        history = game.get("history") or {}
        # Need each agent's belief and the opponent's realised strategy.
        rounds = sorted(
            ((int(k.split("_")[1]), v) for k, v in history.items() if k.startswith("round_")),
            key=lambda t: t[0],
        )
        for round_num, entries in rounds:
            agents_in_round = {e["agent"]: e for e in entries}
            for agent_name, entry in agents_in_round.items():
                belief = entry.get("belief")
                if not belief:
                    continue
                # 2-player: the other entry holds the realised strategy key.
                opponents = [n for n in agents_in_round if n != agent_name]
                if not opponents:
                    continue
                opp = agents_in_round[opponents[0]]
                opp_strategy_label = opp.get("strategy")
                if opp_strategy_label is None:
                    continue
                # We need the opponent's strategy KEY (strategy1/strategy2)
                desc = game.get("description", {})
                matrix_summary = desc.get("payoff_matrix_summary") or {}
                strategies_per_lang = matrix_summary.get("strategies") or {}
                lang = desc.get("language") or "en"
                labels_to_keys = {
                    label: key
                    for key, label in (strategies_per_lang.get(lang) or {}).items()
                }
                opp_key = labels_to_keys.get(opp_strategy_label)
                if opp_key is None:
                    continue
                brier = sum(
                    (float(p) - (1.0 if k == opp_key else 0.0)) ** 2
                    for k, p in belief.items()
                )
                rows.append(
                    {
                        "game_id": game_id,
                        "agent": agent_name,
                        "round": round_num,
                        "brier": brier,
                    }
                )
    if not rows:
        return None
    df = pd.DataFrame(rows)
    summary = df.groupby(["agent", "round"], as_index=False)["brier"].mean()
    fig = px.line(
        summary,
        x="round",
        y="brier",
        color="agent",
        markers=True,
        color_discrete_sequence=_PALETTE,
    )
    fig.update_yaxes(range=[0, 2])
    return _layout(fig, "Belief-accuracy (Brier) per round — lower is better")


def multi_seed_scores_with_ci(df: pd.DataFrame) -> Optional[go.Figure]:
    """Render mean ± CI for each agent's average score, when available."""
    cols = [c for c in df.columns if c.startswith("agent") and c.endswith("_scores_mean")]
    ci_cols = [c.replace("_mean", "_ci_half_width") for c in cols]
    if not cols or not all(c in df.columns for c in ci_cols):
        return None
    means = [float(df[c].iloc[0]) for c in cols]
    cis = [float(df[c].iloc[0]) for c in ci_cols]
    labels = [c.replace("_scores_mean", "") for c in cols]
    fig = go.Figure(
        go.Bar(
            x=labels,
            y=means,
            error_y=dict(type="data", array=cis, visible=True),
            marker_color=_PALETTE,
        )
    )
    return _layout(fig, "Per-agent mean score (with 95% CI across seeds)")
