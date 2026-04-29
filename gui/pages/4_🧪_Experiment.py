"""Experiment-manifest builder: bundle multiple configs + multi-seed reruns."""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import json  # noqa: E402
import tempfile  # noqa: E402

import streamlit as st  # noqa: E402

from gui.components.presets import usable_presets  # noqa: E402
from gui.components.state import init_page  # noqa: E402
from src.experiment import Manifest, run_manifest  # noqa: E402

init_page("Experiment", icon="🧪")

st.title("🧪 Experiment manifest")
st.caption(
    "Run the same suite of configs multiple times — useful for ablations, "
    "language sweeps, or any study that benefits from replication."
)

# ---- Pick configs --------------------------------------------------------

st.markdown("### Configs in the experiment")
presets = usable_presets()
preset_choices = {p.name: str(p.config_path) for p in presets}

cols = st.columns([3, 2])
chosen = cols[0].multiselect(
    "Pick from the shipped scenarios",
    options=list(preset_choices.keys()),
    default=list(preset_choices.keys())[:1],
)

uploaded_paths: list[str] = []
extra_files = cols[1].file_uploader(
    "…or upload custom configs",
    type=["json"],
    accept_multiple_files=True,
)
if extra_files:
    upload_dir = Path(tempfile.gettempdir()) / "fairgame_uploads"
    upload_dir.mkdir(exist_ok=True)
    for uf in extra_files:
        target = upload_dir / uf.name
        target.write_bytes(uf.read())
        uploaded_paths.append(str(target))

config_paths = [preset_choices[name] for name in chosen] + uploaded_paths
if not config_paths:
    st.warning("Pick at least one config to run.")
    st.stop()

# ---- Experiment-level knobs ---------------------------------------------

st.markdown("### Replication & overrides")
cols = st.columns(3)
seed_count = int(
    cols[0].number_input("Seed count per config", min_value=1, max_value=50, value=5)
)
n_rounds_override = int(
    cols[1].number_input("nRounds override (0 = leave per-config)", min_value=0, max_value=200, value=0)
)
aggregate = cols[2].checkbox("Aggregate seeds (mean ± 95% CI)", value=True)

experiment_name = st.text_input("Experiment name", value="my_experiment")
output_dir = st.text_input(
    "Output directory",
    value=str(Path("results") / "gui" / "experiments" / experiment_name),
    help="Per-config CSVs + manifest_summary.json land here.",
)

# ---- Manifest preview ---------------------------------------------------

manifest_dict = {
    "experiment_name": experiment_name,
    "output_dir": output_dir,
    "configs": config_paths,
    "seeds": list(range(seed_count)),
    "aggregate_seeds": aggregate,
}
if n_rounds_override > 0:
    manifest_dict["config_overrides"] = {"nRounds": n_rounds_override}

with st.expander("Manifest preview"):
    st.json(manifest_dict, expanded=False)

manifest_json = json.dumps(manifest_dict, indent=2, ensure_ascii=False)
st.download_button(
    "Download manifest.json",
    data=manifest_json,
    file_name="manifest.json",
    mime="application/json",
)

# ---- Run -----------------------------------------------------------------

if st.button("Run experiment", type="primary"):
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as fh:
        fh.write(manifest_json)
        manifest_path = Path(fh.name)

    with st.status("Running…", expanded=True) as status:
        try:
            manifest = Manifest.load(manifest_path)
            written = run_manifest(manifest)
        except Exception as exc:  # noqa: BLE001
            status.update(label="Experiment failed", state="error")
            st.exception(exc)
            st.stop()
        status.update(label="Experiment complete", state="complete")

    st.success(f"Wrote {len(written)} files to {manifest.output_dir}.")
    st.markdown("##### Outputs")
    for stem, path in written.items():
        st.markdown(f"- `{stem}` → `{path}`")
