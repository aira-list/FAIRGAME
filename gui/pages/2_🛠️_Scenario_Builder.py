"""Scenario builder: tabs for every config dimension, with live preview."""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import json  # noqa: E402

import streamlit as st  # noqa: E402

from gui.components.forms import (  # noqa: E402
    agents_form,
    basics_form,
    game_theory_form,
    replay_form,
    tom_form,
)
from gui.components.presets import usable_presets  # noqa: E402
from gui.components.runner import run_config  # noqa: E402
from gui.components.state import (  # noqa: E402
    get_config_draft,
    init_page,
    set_config_draft,
    set_last_run,
)

init_page("Scenario Builder", icon="🛠️")

st.title("🛠️ Scenario Builder")
st.caption(
    "Compose a full FAIRGAME config from forms — no JSON editing required. "
    "Switch tabs to layer in Theory-of-Mind features, mixed strategies, "
    "discount factors, and multi-seed reruns."
)

# ---- Initial config bootstrap -------------------------------------------

with st.sidebar:
    st.markdown("##### Starting point")
    presets = usable_presets()
    options = ["(blank)"] + [p.name for p in presets]
    pick = st.selectbox(
        "Load preset",
        options=options,
        index=0,
        help="Pre-fills the forms with a shipped scenario.",
    )
    if st.button("Apply preset", use_container_width=True):
        if pick == "(blank)":
            set_config_draft(_blank_config())
        else:
            preset = presets[options.index(pick) - 1]
            set_config_draft(preset.load())
        st.rerun()

    uploaded = st.file_uploader("…or upload a config", type=["json"])
    if uploaded is not None:
        try:
            cfg = json.loads(uploaded.read().decode("utf-8"))
            set_config_draft(cfg)
            st.success("Config loaded.")
            st.rerun()
        except Exception as exc:  # noqa: BLE001
            st.error(f"Could not parse JSON: {exc}")


def _blank_config() -> dict:
    return {
        "name": "Custom scenario",
        "nRounds": 1,
        "nRoundsIsKnown": True,
        "languages": ["en"],
        "allAgentPermutations": False,
        "agents": {
            "names": ["agent1", "agent2"],
            "personalities": {"en": ["cooperative", "selfish"]},
            "opponentPersonalityProb": [0, 0],
        },
        "llms": {"agent1": "OpenAIGPT4o", "agent2": "OpenAIGPT4o"},
        "promptTemplate": {
            "en": (
                "You are {currentPlayerName} and your opponent is {opponent1}.\n"
                "{intro}: [You are {personality}.]\n\n"
                "Choose between {strategy1} and {strategy2}. Output ONLY the choice."
            )
        },
        "payoffMatrix": {
            "weights": {"weight1": 6, "weight2": 10, "weight3": 0, "weight4": 2},
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
    }


config = get_config_draft() or _blank_config()

# ---- Tabs ---------------------------------------------------------------

tabs = st.tabs(
    ["Basics", "Agents", "Theory of Mind", "Game theory", "Reproducibility", "Run"]
)

with tabs[0]:
    config = basics_form(config)
with tabs[1]:
    config = agents_form(config)
with tabs[2]:
    config = tom_form(config)
with tabs[3]:
    config = game_theory_form(config)
with tabs[4]:
    config = replay_form(config)

# Persist the latest edits between reruns.
set_config_draft(config)

with tabs[5]:
    st.markdown("##### Effective config")
    st.json(config, expanded=False)

    download_cols = st.columns([1, 1, 2])
    download_cols[0].download_button(
        "Download config.json",
        data=json.dumps(config, indent=2, ensure_ascii=False),
        file_name="fairgame_config.json",
        mime="application/json",
        use_container_width=True,
    )
    if download_cols[1].button("Reset to blank", use_container_width=True):
        set_config_draft(_blank_config())
        st.rerun()

    st.divider()
    label = st.text_input("Run label", value=config.get("name", "Custom scenario"))
    if st.button("Run scenario", type="primary"):
        with st.status("Running…", expanded=True) as status:
            try:
                outcome = run_config(config, display_name=label)
            except Exception as exc:  # noqa: BLE001
                status.update(label="Run failed", state="error")
                st.exception(exc)
                st.stop()
            status.update(label="Run complete", state="complete")
            set_last_run(outcome.to_session_payload())

        st.success(f"Wrote {outcome.output_dir}.")
        st.dataframe(outcome.df, use_container_width=True)
        st.info("Open the **Results** page to explore the run interactively.")
