"""FAIRGAME — Streamlit GUI entry point.

Run with::

    streamlit run gui/app.py

Streamlit will auto-discover the pages under ``gui/pages/`` and render
them in the sidebar in numeric order.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Streamlit puts the script's directory on sys.path, so absolute imports
# like ``from gui.components...`` only resolve once we add the project root.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st  # noqa: E402

from gui.components.payoff_diagram import render_2x2_payoff_html  # noqa: E402
from gui.components.presets import (  # noqa: E402
    categories,
    usable_by_category,
    usable_presets,
)
from gui.components.runner import list_past_runs  # noqa: E402
from gui.components.state import init_page  # noqa: E402

init_page("Home", icon="🎯")

# ---- Hero ---------------------------------------------------------------

st.markdown(
    """
    <div class="fg-hero">
      <h1>FAIRGAME · Multi-agent game-theoretic studio</h1>
      <p>Design experiments, run them on real or simulated LLM agents, and
      explore the behavioural results — all without writing a single line of code.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---- First-run welcome --------------------------------------------------

if not st.session_state.get("welcome_dismissed"):
    cols = st.columns([5, 1])
    with cols[0]:
        st.info(
            "👋 **First time here?** Read **📖 Guide** in the sidebar for a "
            "5-minute walkthrough, or jump straight to **🚀 Quick start** "
            "and run any scenario — Demo mode is on, so no API keys are needed."
        )
    if cols[1].button("Got it", key="dismiss_welcome"):
        st.session_state["welcome_dismissed"] = True
        st.rerun()

# ---- "Get started" cards ------------------------------------------------

st.markdown("## Get started", unsafe_allow_html=False)
cols = st.columns(3)
cards = [
    {
        "title": "🚀 Quick start",
        "body": (
            "Pick one of the shipped scenarios — Prisoner's Dilemma, "
            "Stag Hunt, or a Theory-of-Mind variant — and run it in a single "
            "click."
        ),
    },
    {
        "title": "🛠️ Build a scenario",
        "body": (
            "Custom personality / payoff / model setups via guided forms. "
            "Advanced features (ToM, mixed strategies, discount factors) are "
            "tucked behind a toggle."
        ),
    },
    {
        "title": "🏆 Run a tournament",
        "body": (
            "Stage a round-robin between LLM agents and the canonical baseline "
            "strategies (Tit-for-Tat, Grim Trigger, …)."
        ),
    },
]
for col, card in zip(cols, cards):
    with col:
        st.markdown(
            f"""
            <div class="fg-card">
              <h3>{card['title']}</h3>
              <p>{card['body']}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.write("")
cols2 = st.columns(2)
with cols2[0]:
    st.markdown(
        """
        <div class="fg-card">
          <h3>🧪 Run an experiment</h3>
          <p>Bundle multiple configs + multi-seed reruns into a single
          manifest. Per-config CSVs and confidence-interval tables are
          written automatically.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
with cols2[1]:
    st.markdown(
        """
        <div class="fg-card">
          <h3>📊 Explore results</h3>
          <p>Browse every past run, view the per-game DataFrame and
          interactive Plotly charts: cooperation rate, score, welfare,
          equilibrium-rate distribution, Brier score, multi-seed CIs.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ---- "Shipped scenarios" gallery, grouped by category ------------------

st.write("")
st.markdown("## Shipped scenarios")
all_categories = categories()
if not all_categories:
    st.info("No scenarios found under `resources/config/`.")
else:
    for category in all_categories:
        presets = usable_by_category(category)
        if not presets:
            continue
        st.markdown(f"### {category}")
        cols = st.columns(min(2, len(presets)))
        for idx, preset in enumerate(presets):
            col = cols[idx % len(cols)]
            with col:
                tags_html = "".join(
                    f"<span class='fg-pill fg-pill-blue'>{tag}</span>"
                    for tag in preset.tags
                )
                diagram = render_2x2_payoff_html(preset.load())
                st.markdown(
                    f"""
                    <div class="fg-card">
                      <h3>{preset.name}</h3>
                      <p>{preset.summary}</p>
                      <div style='margin-top: 0.6rem'>{tags_html}</div>
                      {diagram}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

# ---- "Recent runs" section ---------------------------------------------

st.write("")
st.markdown("## Recent runs on this machine")
runs = list_past_runs()
if not runs:
    st.caption("No runs yet — start one from the Quick start page.")
else:
    for run in runs[:8]:
        st.markdown(f"- `{run.name}` · `{run}`")
