"""Quick-start page: pick a shipped scenario and run it in one click."""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st  # noqa: E402

from gui.components.payoff_diagram import render_2x2_payoff_html  # noqa: E402
from gui.components.presets import categories, usable_by_category  # noqa: E402
from gui.components.runner import run_config  # noqa: E402
from gui.components.state import init_page, set_config_draft, set_last_run  # noqa: E402

init_page("Quick start", icon="🚀")

st.title("🚀 Quick start")
st.caption(
    "Pick a built-in scenario, optionally tweak the seed, and click Run. "
    "Demo mode (sidebar toggle) decides whether real LLMs are called."
)

# ---- Two-tier menu: category → scenario --------------------------------

cats = categories()
if not cats:
    st.error("No shipped scenarios available — `resources/config/` is empty.")
    st.stop()

cols = st.columns([1, 2])
chosen_category = cols[0].selectbox(
    "Category",
    options=cats,
    index=0,
    help=(
        "Pick a family of experiments. **Classic games** is the right "
        "starting point — those are the canonical Prisoner's Dilemma / "
        "Stag Hunt / etc. without any extras."
    ),
)
presets_in_category = usable_by_category(chosen_category)

if not presets_in_category:
    st.warning(f"No scenarios in '{chosen_category}'.")
    st.stop()

scenario_names = [p.name for p in presets_in_category]
chosen_name = cols[1].selectbox(
    "Scenario",
    options=scenario_names,
    index=0,
)
preset = presets_in_category[scenario_names.index(chosen_name)]

config = preset.load()

# ---- Description card with optional payoff thumbnail --------------------

with st.expander("Scenario details", expanded=True):
    st.markdown(f"**{preset.name}** — {preset.summary}")
    pills = "".join(
        f"<span class='fg-pill fg-pill-blue'>{tag}</span>" for tag in preset.tags
    )
    st.markdown(pills, unsafe_allow_html=True)

    diagram = render_2x2_payoff_html(config)
    if diagram:
        st.markdown(
            "<div style='margin-top:0.6rem;color:#64748b;font-size:0.82rem'>"
            "Payoff matrix (row=you, column=opponent; "
            "<span style='color:#1d4ed8'>your payoff</span> / "
            "<span style='color:#be123c'>opponent's payoff</span>):</div>"
            + diagram,
            unsafe_allow_html=True,
        )

# ---- Run knobs ----------------------------------------------------------

cols = st.columns([2, 1, 1])
display_name = cols[0].text_input(
    "Run label",
    value=preset.name,
    help="Used in result filenames so you can find the run later.",
)
seed_count = int(
    cols[1].number_input(
        "Repetitions (seed count)",
        min_value=1,
        max_value=20,
        value=int(config.get("seedCount") or 1),
        help=(
            "Run the experiment this many times with different random "
            "seeds. Set > 1 to get confidence intervals in the results."
        ),
    )
)
seed = int(
    cols[2].number_input(
        "Master seed (0 = random)",
        min_value=0,
        max_value=10**6,
        value=int(config.get("seed") or 0),
        help=(
            "Pin the engine's randomness so the same seed gives the same "
            "result. Use 0 for nondeterministic runs."
        ),
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

with st.expander("Show raw config (advanced)"):
    st.json(config, expanded=False)

# ---- Run ---------------------------------------------------------------

if st.button("Run scenario", type="primary"):
    with st.status("Running…", expanded=True) as status:
        try:
            outcome = run_config(config, display_name=display_name)
        except Exception as exc:  # noqa: BLE001
            status.update(label="Run failed", state="error")
            st.exception(exc)
            st.stop()
        status.update(label="Run complete", state="complete")
        set_last_run(outcome.to_session_payload())
        set_config_draft(config)

    st.success(f"Wrote {outcome.output_dir}.")
    st.dataframe(outcome.df, use_container_width=True)
    st.info("Open the **Results** page in the sidebar to explore the run interactively.")
