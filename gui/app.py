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

from gui.components.presets import usable_presets  # noqa: E402
from gui.components.runner import list_past_runs  # noqa: E402
from gui.components.state import init_page  # noqa: E402

init_page("Home", icon="🎯")

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

# ---- "Quick start" section ---------------------------------------------

st.markdown("## Get started", unsafe_allow_html=False)
cols = st.columns(3)
cards = [
    {
        "title": "🚀 Quick start",
        "body": (
            "Pick one of the shipped scenarios — Prisoner's Dilemma, "
            "Volunteer's Dilemma, or a Theory-of-Mind variant — and run it "
            "in a single click."
        ),
        "page": "1_🚀_Quick_Start",
    },
    {
        "title": "🛠️ Build a scenario",
        "body": (
            "Custom personality / payoff / model setups via guided forms. "
            "Toggle ToM, mixed strategies, discount factors, utility transforms "
            "and more."
        ),
        "page": "2_🛠️_Scenario_Builder",
    },
    {
        "title": "🏆 Run a tournament",
        "body": (
            "Stage a round-robin between LLM agents and the canonical baseline "
            "strategies (TitForTat, GrimTrigger, …)."
        ),
        "page": "3_🏆_Tournament",
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

# ---- "Available scenarios" section -------------------------------------

st.write("")
st.markdown("## Shipped scenarios")
presets = usable_presets()
if not presets:
    st.info("No scenarios found under `resources/config/`.")
else:
    pres_cols = st.columns(min(2, len(presets)))
    for idx, preset in enumerate(presets):
        col = pres_cols[idx % len(pres_cols)]
        with col:
            tags_html = "".join(
                f"<span class='fg-pill fg-pill-blue'>{tag}</span>"
                for tag in preset.tags
            )
            st.markdown(
                f"""
                <div class="fg-card">
                  <h3>{preset.name}</h3>
                  <p>{preset.summary}</p>
                  <div style='margin-top: 0.6rem'>{tags_html}</div>
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
