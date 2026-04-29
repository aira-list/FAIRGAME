"""Quick-start page: pick a shipped scenario and run it in one click."""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st  # noqa: E402

from gui.components.presets import usable_presets  # noqa: E402
from gui.components.runner import run_config  # noqa: E402
from gui.components.state import init_page, set_config_draft, set_last_run  # noqa: E402

init_page("Quick start", icon="🚀")

st.title("🚀 Quick start")
st.caption(
    "Pick a built-in scenario, optionally edit the description, and run it. "
    "Demo mode (sidebar toggle) decides whether real LLMs are called."
)

presets = usable_presets()
if not presets:
    st.error("No shipped scenarios available — `resources/config/` is empty.")
    st.stop()

names = [f"{p.name}" for p in presets]
choice = st.selectbox("Scenario", names, index=0)
preset = presets[names.index(choice)]

config = preset.load()

with st.expander("Scenario details", expanded=True):
    st.markdown(f"**{preset.name}** — {preset.summary}")
    pills = "".join(
        f"<span class='fg-pill fg-pill-blue'>{tag}</span>" for tag in preset.tags
    )
    st.markdown(pills, unsafe_allow_html=True)

cols = st.columns([2, 1, 1])
display_name = cols[0].text_input("Run label", value=preset.name)
seed_count = int(
    cols[1].number_input(
        "Seed count", min_value=1, max_value=20, value=int(config.get("seedCount") or 1)
    )
)
seed = int(
    cols[2].number_input(
        "Master seed (0 ⇒ none)", min_value=0, max_value=10**6, value=int(config.get("seed") or 0)
    )
)

if seed_count > 1:
    config["seedCount"] = seed_count
else:
    config.pop("seedCount", None)
if seed > 0:
    config["seed"] = seed
else:
    config.pop("seed", None)

st.markdown("##### Effective config preview")
st.json(config, expanded=False)

if st.button("Run scenario", type="primary"):
    with st.status("Running…", expanded=True) as status:
        try:
            outcome = run_config(config, display_name=display_name)
        except Exception as exc:  # noqa: BLE001 — we want to surface the message verbatim.
            status.update(label="Run failed", state="error")
            st.exception(exc)
            st.stop()
        status.update(label="Run complete", state="complete")
        set_last_run(outcome.to_session_payload())
        set_config_draft(config)

    st.success(f"Wrote {outcome.output_dir}.")
    st.dataframe(outcome.df, use_container_width=True)
    st.info("Open the **Results** page in the sidebar to explore the run interactively.")
