"""Cross-run comparison: pick 2+ past runs and overlay them.

Useful for ablation studies — e.g. ToM order 0 vs 1 vs 2 of the same
scenario, or the same scenario across languages.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st  # noqa: E402

from gui.components.plots import (  # noqa: E402
    overlay_cooperation_rate,
    overlay_metric_bars,
)
from gui.components.runner import list_past_runs, load_past_run  # noqa: E402
from gui.components.state import init_page  # noqa: E402
from src.results_processing.stats import (  # noqa: E402
    compare_metrics,
    default_comparison_metrics,
)

init_page("Compare runs", icon="⚖️")

st.title("⚖️ Compare runs")
st.caption(
    "Pick two or more past runs to overlay their cooperation curves and "
    "test whether scalar metrics differ significantly between them."
)

runs = list_past_runs()
if len(runs) < 2:
    st.info(
        "You need at least two past runs to compare. Run a couple of "
        "scenarios from Quick Start first."
    )
    st.stop()

run_labels = [r.name for r in runs]
chosen = st.multiselect(
    "Pick runs to compare",
    options=run_labels,
    default=run_labels[:2],
    help="Select 2 or more. Each becomes a separate trace in the overlay.",
)

if len(chosen) < 2:
    st.warning("Select at least two runs.")
    st.stop()

loaded: list[dict] = []
for name in chosen:
    run_dir = runs[run_labels.index(name)]
    try:
        outcome = load_past_run(run_dir)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not load {run_dir}: {exc}")
        continue
    loaded.append(
        {
            "label": outcome.name,
            "df": outcome.df,
            "raw": outcome.raw,
        }
    )

if len(loaded) < 2:
    st.warning("At least two runs must load successfully.")
    st.stop()

# ---- Overlay charts -----------------------------------------------------

st.markdown("### Cooperation rate")
fig = overlay_cooperation_rate(loaded)
if fig is not None:
    st.plotly_chart(fig, use_container_width=True)
else:
    st.caption("No cooperation-rate data available for these runs.")

cols = st.columns(2)
welfare_fig = overlay_metric_bars(
    loaded, "welfare_mean_sum", "Welfare (mean joint payoff)"
)
if welfare_fig is not None:
    cols[0].plotly_chart(welfare_fig, use_container_width=True)
eq_fig = overlay_metric_bars(loaded, "equilibrium_rate", "Equilibrium rate")
if eq_fig is not None:
    cols[1].plotly_chart(eq_fig, use_container_width=True)

# ---- Pairwise hypothesis tests ------------------------------------------

st.markdown("### Statistical comparison")
st.caption(
    "Welch's t-test (parametric) and Mann–Whitney U (rank-based, "
    "distribution-free). Both are two-sided. Use Welch when the metric "
    "looks roughly normal; reach for Mann–Whitney otherwise."
)

if len(loaded) > 2:
    pair_options = [(loaded[0]["label"], r["label"]) for r in loaded[1:]]
else:
    pair_options = [(loaded[0]["label"], loaded[1]["label"])]

label_a = st.selectbox(
    "Run A",
    options=[r["label"] for r in loaded],
    index=0,
)
label_b = st.selectbox(
    "Run B",
    options=[r["label"] for r in loaded if r["label"] != label_a],
    index=0,
)

run_a = next(r for r in loaded if r["label"] == label_a)
run_b = next(r for r in loaded if r["label"] == label_b)
metrics_available = sorted(
    set(default_comparison_metrics(run_a["df"]) + default_comparison_metrics(run_b["df"]))
)

if not metrics_available:
    st.info(
        "No comparable scalar metrics found. Multi-seed runs (`seedCount > 1`) "
        "produce richer comparisons."
    )
else:
    metrics = st.multiselect(
        "Metrics to compare",
        options=metrics_available,
        default=metrics_available[:5],
    )
    if metrics:
        comparison_df = compare_metrics(run_a["df"], run_b["df"], metrics)
        st.dataframe(comparison_df, use_container_width=True)
        st.caption(
            "p-value < 0.05 (the conventional threshold) means the "
            "difference between A and B's metric distributions is unlikely "
            "to be noise."
        )
