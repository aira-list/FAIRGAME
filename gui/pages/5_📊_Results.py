"""Results explorer: browse past runs and visualise them interactively."""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import json  # noqa: E402

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from gui.components.plots import (  # noqa: E402
    brier_per_round,
    cooperation_rate_per_round,
    equilibrium_rate_bar,
    multi_seed_scores_with_ci,
    score_per_round,
    welfare_breakdown,
)
from gui.components.runner import list_past_runs, load_past_run  # noqa: E402
from gui.components.state import init_page  # noqa: E402

init_page("Results", icon="📊")

st.title("📊 Results explorer")
st.caption("Browse every run on this machine. Click a row to load its plots.")

runs = list_past_runs()
if not runs:
    st.info("No runs yet. Start one from the Quick Start, Builder, or Tournament page.")
    st.stop()

# ---- Run picker ----------------------------------------------------------

labels = [f"{p.name}" for p in runs]
choice = st.selectbox("Pick a run", labels, index=0)
run_dir = runs[labels.index(choice)]

try:
    outcome = load_past_run(run_dir)
except Exception as exc:  # noqa: BLE001
    st.error(f"Could not load {run_dir}: {exc}")
    st.stop()

# ---- Header card ---------------------------------------------------------

cfg = outcome.config
agents_block = (cfg.get("agents") or {}).get("names", [])
pills = []
if cfg.get("tournament", {}).get("enabled"):
    pills.append("<span class='fg-pill fg-pill-amber'>Tournament</span>")
if cfg.get("elicitBeliefs"):
    pills.append("<span class='fg-pill fg-pill-violet'>ToM</span>")
if cfg.get("mixedStrategies"):
    pills.append("<span class='fg-pill fg-pill-rose'>Mixed strategies</span>")
if cfg.get("seedCount", 0) > 1 or cfg.get("seeds"):
    pills.append("<span class='fg-pill fg-pill-green'>Multi-seed</span>")
pills.append(f"<span class='fg-pill fg-pill-slate'>{len(outcome.raw)} games</span>")
pills.append(
    f"<span class='fg-pill fg-pill-blue'>{cfg.get('nRounds', '?')} rounds</span>"
)
if agents_block:
    pills.append(
        f"<span class='fg-pill fg-pill-slate'>{len(agents_block)} agents</span>"
    )

st.markdown(
    f"""
    <div class="fg-card">
      <h3>{outcome.name}</h3>
      <p style='color:#64748b;font-size:0.9rem'>{outcome.timestamp} · {outcome.output_dir}</p>
      <div style='margin-top:0.6rem'>{' '.join(pills)}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---- Tabs ----------------------------------------------------------------

tabs = st.tabs(["Charts", "DataFrame", "Raw history", "Config"])

with tabs[0]:
    cols = st.columns(2)
    with cols[0]:
        fig = cooperation_rate_per_round(outcome.raw)
        if fig is not None:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("Cooperation rate could not be computed for this run.")
    with cols[1]:
        fig = score_per_round(outcome.raw)
        if fig is not None:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("Score-per-round chart unavailable.")

    cols2 = st.columns(2)
    with cols2[0]:
        fig = welfare_breakdown(outcome.df)
        if fig is not None:
            st.plotly_chart(fig, use_container_width=True)
    with cols2[1]:
        fig = equilibrium_rate_bar(outcome.df)
        if fig is not None:
            st.plotly_chart(fig, use_container_width=True)

    fig = brier_per_round(outcome.raw)
    if fig is not None:
        st.plotly_chart(fig, use_container_width=True)

    if outcome.aggregated is not None:
        fig = multi_seed_scores_with_ci(outcome.aggregated)
        if fig is not None:
            st.plotly_chart(fig, use_container_width=True)

with tabs[1]:
    st.dataframe(outcome.df, use_container_width=True, height=520)
    st.download_button(
        "Download results.csv",
        data=outcome.df.to_csv(index=False).encode("utf-8"),
        file_name=f"{outcome.name}_results.csv",
        mime="text/csv",
    )
    if outcome.aggregated is not None:
        st.markdown("##### Multi-seed aggregate")
        st.dataframe(outcome.aggregated, use_container_width=True, height=300)

with tabs[2]:
    st.caption(
        "Raw per-game histories returned by the engine. Useful for ad-hoc "
        "introspection."
    )
    for game_id, game in outcome.raw.items():
        with st.expander(game_id, expanded=False):
            st.json(game, expanded=False)

with tabs[3]:
    st.markdown("##### Stored config")
    st.json(outcome.config, expanded=False)
    st.download_button(
        "Download config.json",
        data=json.dumps(outcome.config, indent=2, ensure_ascii=False),
        file_name=f"{outcome.name}_config.json",
        mime="application/json",
    )
