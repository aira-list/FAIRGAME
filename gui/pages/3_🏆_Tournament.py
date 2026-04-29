"""Round-robin tournament builder: pick contestants, watch them duel."""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st  # noqa: E402

from gui.components.forms import llm_choices  # noqa: E402
from gui.components.runner import run_config  # noqa: E402
from gui.components.state import init_page, set_last_run  # noqa: E402

init_page("Tournament", icon="🏆")

st.title("🏆 Round-robin tournament")
st.caption(
    "Each contestant plays every other contestant once (NC2 games). Mix LLM "
    "agents and the canonical baseline strategies (TitForTat, GrimTrigger, "
    "AlwaysCooperate, …) to benchmark behaviour against well-known controls."
)

# ---- Build the contestant roster ----------------------------------------

st.markdown("### Contestants")
default_models = [
    "Baseline:AlwaysCooperate",
    "Baseline:AlwaysDefect",
    "Baseline:TitForTat",
    "Baseline:GrimTrigger",
]
options = llm_choices()
selected = st.multiselect(
    "Pick at least 2 contestants",
    options=options,
    default=[m for m in default_models if m in options],
    help="Each contestant becomes one agent. Order is preserved.",
)

if len(selected) < 2:
    st.warning("Pick at least two contestants to stage a match.")
    st.stop()

# Auto-derive friendly agent names from the model identifier.
agent_names = []
for model in selected:
    base = model.replace("Baseline:", "").replace("OpenAI", "openai_")
    name = base.lower()
    while name in agent_names:
        name = f"{name}_{agent_names.count(name) + 1}"
    agent_names.append(name)

# ---- Game knobs ----------------------------------------------------------

st.markdown("### Match settings")
cols = st.columns([1, 1, 1])
n_rounds = int(
    cols[0].number_input("Rounds per match", min_value=1, max_value=200, value=10)
)
discount = float(
    cols[1].slider("Discount factor δ", 0.50, 1.00, 0.95, step=0.05)
)
seed_count = int(
    cols[2].number_input("Seed count", min_value=1, max_value=20, value=3,
                          help="Re-run the entire tournament this many times for confidence intervals."),
)

st.markdown("### Payoff matrix")
st.caption("Penalty = lower is better. Defaults match the classic Prisoner's Dilemma.")
mc = st.columns(4)
weights = [
    int(mc[0].number_input("Both Cooperate", value=6, min_value=0)),
    int(mc[1].number_input("Sucker pays", value=10, min_value=0)),
    int(mc[2].number_input("Temptation gets", value=0, min_value=0)),
    int(mc[3].number_input("Both Defect", value=2, min_value=0)),
]

label = st.text_input("Tournament label", value="Round-robin tournament")

if st.button("Run tournament", type="primary"):
    config = {
        "name": label,
        "nRounds": n_rounds,
        "nRoundsIsKnown": True,
        "languages": ["en"],
        "allAgentPermutations": False,
        "tournament": {"enabled": True, "mode": "round_robin", "symmetric": True},
        "baselineSemantics": {"cooperate": "strategy1", "defect": "strategy2"},
        "agents": {
            "names": agent_names,
            "personalities": {"en": ["None"] * len(agent_names)},
            "opponentPersonalityProb": [0] * len(agent_names),
        },
        "llms": dict(zip(agent_names, selected)),
        "promptTemplate": {
            "en": (
                "You are {currentPlayerName} and your opponent is {opponent1}.\n"
                "Each round, choose between {strategy1} and {strategy2}.\n"
                "If you both choose {strategy1}, you both get a penalty of {weight1}.\n"
                "If you choose {strategy1} and {opponent1} chooses {strategy2}, "
                "you get a penalty of {weight2} and {opponent1} gets a penalty of {weight3}.\n"
                "If you choose {strategy2} and {opponent1} chooses {strategy1}, "
                "you get a penalty of {weight3} and {opponent1} gets a penalty of {weight2}.\n"
                "If you both choose {strategy2}, you both get a penalty of {weight4}.\n"
                "{choose}: [Output only your choice.]"
            )
        },
        "payoffMatrix": {
            "weights": {
                "weight1": weights[0],
                "weight2": weights[1],
                "weight3": weights[2],
                "weight4": weights[3],
            },
            "strategies": {"en": {"strategy1": "Cooperate", "strategy2": "Defect"}},
            "combinations": {
                "combination1": ["strategy1", "strategy1"],
                "combination2": ["strategy1", "strategy2"],
                "combination3": ["strategy2", "strategy1"],
                "combination4": ["strategy2", "strategy2"],
            },
            "matrix": {
                "combination1": ["weight1", "weight1"],
                "combination2": ["weight3", "weight2"],
                "combination3": ["weight2", "weight3"],
                "combination4": ["weight4", "weight4"],
            },
        },
        "stopGameWhen": [],
        "agentsCommunicate": False,
        "discountFactor": discount,
        "equilibria": ["combination4"],
    }
    if seed_count > 1:
        config["seedCount"] = seed_count

    with st.status("Running tournament…", expanded=True) as status:
        try:
            outcome = run_config(config, display_name=label)
        except Exception as exc:  # noqa: BLE001
            status.update(label="Tournament failed", state="error")
            st.exception(exc)
            st.stop()
        status.update(label="Tournament complete", state="complete")
        set_last_run(outcome.to_session_payload())

    st.success(f"{len(outcome.raw)} games played, results in {outcome.output_dir}.")
    st.dataframe(outcome.df, use_container_width=True)
    st.info(
        "Open the **Results** page in the sidebar to inspect cooperation rates "
        "and welfare per matchup."
    )
