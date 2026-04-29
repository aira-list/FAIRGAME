"""Friendly walkthrough for first-time users.

This page is intentionally jargon-light. It answers "what is FAIRGAME and
how do I use it?" before sending the reader off to the action pages.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st  # noqa: E402

from gui.components.state import init_page  # noqa: E402

init_page("Guide", icon="📖")

st.title("📖 Guide")
st.caption(
    "A short tour of FAIRGAME. Read this first; everything else in the "
    "sidebar gets simpler once these ideas land."
)

# ---- What FAIRGAME does -------------------------------------------------

st.markdown("## What is FAIRGAME?")
st.markdown(
    """
FAIRGAME is a **virtual laboratory** for putting AI agents (large language
models such as GPT-4o, Claude, Mistral) into classical game-theory
scenarios — the Prisoner's Dilemma, the Stag Hunt, the Battle of the Sexes,
and others — and observing how they behave.

The framework was built to answer questions like:

* Do LLM agents cooperate, or do they exploit each other?
* Does behaviour change when we tell the agent its opponent has a
  certain personality?
* Does it change when we ask the question in French instead of English?
* Can a stronger model ("Claude") outsmart a weaker one ("Mistral")
  in a one-shot game?

You design an experiment, FAIRGAME runs it, and you get a table of
choices and scores you can analyse.
"""
)

st.divider()

# ---- The three big switches --------------------------------------------

st.markdown("## The three big switches")
cols = st.columns(3)
with cols[0]:
    st.markdown(
        """
        ### 🟢 Demo mode
        On by default. Every "LLM call" is answered by a fast in-process
        stub, so you can explore the whole tool **without any API keys**
        and **without spending money**.

        Toggle it off in the sidebar when you're ready to run real models.
        """
    )
with cols[1]:
    st.markdown(
        """
        ### 🎯 Pick a game
        FAIRGAME ships with the classics — Prisoner's Dilemma, Stag Hunt,
        Snowdrift, Harmony, Battle of the Sexes, Zero-Sum, Volunteer's
        Dilemma — plus tournament and Theory-of-Mind variants.

        Or build your own from scratch in the **Scenario Builder**.
        """
    )
with cols[2]:
    st.markdown(
        """
        ### 📊 Read the results
        Every run produces a table (one row per game) and interactive
        charts: cooperation rate, scores per round, welfare summaries,
        and (if enabled) belief-accuracy metrics.
        """
    )

st.divider()

# ---- Workflow ----------------------------------------------------------

st.markdown("## The five pages")
st.markdown(
    """
The sidebar offers five pages, listed roughly in order of complexity.
You only need the first one for most experiments.
"""
)

walkthrough = [
    (
        "🚀 Quick start",
        "Pick a built-in scenario, optionally adjust the seed, click **Run**. "
        "Best place to start.",
    ),
    (
        "🛠️ Scenario builder",
        "A guided form for fully custom experiments. The first two tabs "
        "(Basics and Agents) cover 90% of use cases; advanced features "
        "(Theory of Mind, discount factors, utility transforms…) are "
        "tucked behind an *Advanced* toggle.",
    ),
    (
        "🏆 Tournament",
        "Stage a round-robin between any combination of LLM agents and "
        "the canonical baseline strategies (Tit-for-Tat, Grim Trigger, "
        "Always Cooperate, …). Useful for **benchmarking**.",
    ),
    (
        "🧪 Experiment",
        "Run the same set of configs many times with different random "
        "seeds. The output is a CSV with means and 95% confidence "
        "intervals — what you'd want for a paper.",
    ),
    (
        "📊 Results",
        "Browse every run that's ever happened on this machine. Charts, "
        "tables, raw history, downloadable CSV.",
    ),
]
for title, body in walkthrough:
    with st.container(border=True):
        st.markdown(f"**{title}** · {body}")

st.divider()

# ---- Worked example -----------------------------------------------------

st.markdown("## A worked example")
st.markdown(
    """
Imagine you want to know whether GPT-4o cooperates more in English than
in French when playing the Prisoner's Dilemma against a "selfish"
opponent.

1. Open **🚀 Quick start**.
2. Pick **Prisoner's Dilemma — classic** from the dropdown.
3. Set the seed to `42` (so the run is reproducible) and the seed count
   to `5` (so you get confidence intervals).
4. Click **Run scenario**. With Demo mode on this finishes in seconds; in
   live mode it costs about 30 LLM calls.
5. Open **📊 Results**, click your run, and read the *cooperation rate
   per round* chart — one curve per language.

You've just done a cross-lingual bias experiment.
"""
)

st.divider()

# ---- Glossary ----------------------------------------------------------

st.markdown("## Glossary")
glossary = [
    (
        "**Agent**",
        "One participant in the game. Driven by an LLM by default, or by "
        "a *baseline strategy* like Tit-for-Tat.",
    ),
    (
        "**Strategy**",
        "What the agent picks each round. In a Prisoner's Dilemma the "
        "two strategies are usually \"Cooperate\" and \"Defect\".",
    ),
    (
        "**Payoff matrix**",
        "A table that says how many points each agent earns for every "
        "combination of strategies the players might pick.",
    ),
    (
        "**Equilibrium**",
        "A combination of strategies where no agent regrets its move. "
        "Most classical games have one or two of these.",
    ),
    (
        "**Tit-for-Tat (TFT)**",
        "A famous strategy: \"cooperate first, then copy whatever your "
        "opponent did last round\". One of the canonical baselines you "
        "can pit your LLM against.",
    ),
    (
        "**Theory of Mind (ToM)**",
        "Reasoning about what other agents know, believe, or will do. "
        "FAIRGAME can ask the agent to predict its opponent's choice "
        "(belief elicitation) and ablate the level of opponent "
        "information given (ToM order 0, 1, 2).",
    ),
    (
        "**Brier score**",
        "Measures how well-calibrated an agent's predictions were. "
        "Lower is better; 0 means perfect prediction.",
    ),
    (
        "**Discount factor (δ)**",
        "Multiplies each round's payoff by δ^(round - 1). δ < 1 means "
        "future rounds matter less than today — the standard "
        "infinite-horizon model.",
    ),
    (
        "**Utility transform**",
        "Maps raw points into agent satisfaction. Use **CRRA** for "
        "risk aversion, **Fehr-Schmidt** for inequity aversion.",
    ),
    (
        "**Welfare metrics**",
        "How well the *group* did, not just the individual: total "
        "points, the worst-off agent's points (Rawlsian), and the Gini "
        "coefficient of inequality.",
    ),
    (
        "**Tournament**",
        "Round-robin: every agent plays every other agent once. The "
        "standard way to compare strategies head-to-head.",
    ),
    (
        "**Seed**",
        "Pins the random choices the engine makes (type draws, mixed-"
        "strategy sampling, fake-message generation) so the same run "
        "produces the same output. **Seed count > 1** runs the experiment "
        "multiple times for statistical confidence.",
    ),
    (
        "**Covert / random / fake channel**",
        "Optional restricted communication mode where agents trade "
        "10-number sequences instead of free text. Used to test whether "
        "agents can smuggle strategy information through a noisy "
        "channel.",
    ),
]
for term, definition in glossary:
    st.markdown(f"- {term} — {definition}")

st.divider()

# ---- Where to next -----------------------------------------------------

st.markdown("## Where to next")
st.markdown(
    """
- **First time?** Click **🚀 Quick start** in the sidebar.
- **Want something custom?** Open **🛠️ Scenario builder** — start with
  the Basics tab, ignore the Advanced section until you need it.
- **Comparing strategies?** Use **🏆 Tournament**.
- **Writing a paper?** Use **🧪 Experiment** to run with multiple seeds
  and get confidence intervals.
- **Reading old results?** Everything you've ever run is on **📊
  Results**.
"""
)
