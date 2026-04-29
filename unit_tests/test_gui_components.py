"""Tests for the GUI's non-Streamlit helpers.

We don't try to render Streamlit pages from pytest — Streamlit's runtime
is heavyweight and the visual output isn't easily asserted on. Instead we
verify the headless components: presets load, the demo connector swaps
cleanly in and out, plots return ``None`` when data is missing, and the
runner persists results in the expected layout.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

from gui.components import fakes
from gui.components.plots import (
    cooperation_rate_per_round,
    equilibrium_rate_bar,
    multi_seed_scores_with_ci,
    score_per_round,
    welfare_breakdown,
)
from gui.components.presets import CATALOG, by_key, usable_presets
from gui.components.runner import list_past_runs, load_past_run, run_config
from src.llm_connectors import llm_factory_connector


class TestPresets(unittest.TestCase):
    def test_catalog_keys_unique(self) -> None:
        keys = [p.key for p in CATALOG]
        self.assertEqual(len(keys), len(set(keys)))

    def test_each_preset_has_existing_config(self) -> None:
        # Every shipped preset should resolve to a real file on disk.
        for preset in CATALOG:
            self.assertTrue(
                preset.config_path.is_file(),
                msg=f"{preset.key} -> {preset.config_path} missing",
            )

    def test_load_injects_template_when_missing(self) -> None:
        preset = by_key("pd_classic")
        config = preset.load()
        self.assertTrue(
            "templateFilename" in config or "promptTemplate" in config,
            msg="Preset must have a template binding after load.",
        )

    def test_usable_presets_skips_missing_files(self) -> None:
        # Currently every preset exists, but we still want to verify the
        # filter works when one of them goes missing.
        with mock.patch.object(CATALOG[0], "config_path", Path("/no/such/file.json")):
            keys = {p.key for p in usable_presets()}
            self.assertNotIn(CATALOG[0].key, keys)


class TestDemoConnectorSwap(unittest.TestCase):
    def setUp(self) -> None:
        # Snapshot whatever's in the registry *right now* (likely the conftest
        # fake) so we can restore it after the test mutates the registry.
        self._snapshot = dict(llm_factory_connector.MODEL_PROVIDER_MAP)

    def tearDown(self) -> None:
        llm_factory_connector.MODEL_PROVIDER_MAP.clear()
        llm_factory_connector.MODEL_PROVIDER_MAP.update(self._snapshot)
        fakes._DEMO_INSTALLED = False  # reset module flag too

    def test_install_swaps_registry(self) -> None:
        fakes.install_demo_connector()
        for name in ("OpenAIGPT4o", "Claude35Sonnet", "MistralLarge"):
            loader, model = llm_factory_connector.MODEL_PROVIDER_MAP[name]
            self.assertIs(loader(), fakes._DemoConnector)
            self.assertEqual(model, "demo")

    def test_restore_clears_demo_flag(self) -> None:
        fakes.install_demo_connector()
        self.assertTrue(fakes.is_demo_active())
        fakes.restore_real_connectors()
        self.assertFalse(fakes.is_demo_active())
        # Known models are still in the registry (we don't load them, since
        # the real provider SDKs may not be installed in the test env).
        self.assertIn("OpenAIGPT4o", llm_factory_connector.MODEL_PROVIDER_MAP)

    def test_set_demo_mode_idempotent(self) -> None:
        fakes.set_demo_mode(False)
        self.assertFalse(fakes.is_demo_active())
        fakes.set_demo_mode(True)
        self.assertTrue(fakes.is_demo_active())
        # Calling True again is a no-op.
        fakes.set_demo_mode(True)
        self.assertTrue(fakes.is_demo_active())

    def test_demo_belief_prompt_returns_valid_json(self) -> None:
        connector = fakes._DemoConnector()
        prompt = (
            'Predict opponent strategy. Output JSON with probability values: '
            '{"Cooperate": 0.5, "Defect": 0.5}'
        )
        response = connector._send_prompt(prompt)
        self.assertIn("Cooperate", response)
        self.assertIn("Defect", response)


class TestPlotsHandleMissingData(unittest.TestCase):
    """All plot helpers must return None — never raise — on empty inputs."""

    def test_cooperation_rate_returns_none_for_empty_dict(self) -> None:
        self.assertIsNone(cooperation_rate_per_round({}))

    def test_score_per_round_returns_none_for_empty_dict(self) -> None:
        self.assertIsNone(score_per_round({}))

    def test_welfare_breakdown_returns_none_when_no_columns(self) -> None:
        self.assertIsNone(welfare_breakdown(pd.DataFrame()))

    def test_equilibrium_rate_bar_returns_none_when_column_missing(self) -> None:
        self.assertIsNone(equilibrium_rate_bar(pd.DataFrame()))

    def test_multi_seed_returns_none_without_mean_columns(self) -> None:
        self.assertIsNone(multi_seed_scores_with_ci(pd.DataFrame()))


class TestRunnerPersistsArtefacts(unittest.TestCase):
    """A demo-mode run must produce config.json, results.csv, raw_results.json."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="fg_gui_"))
        # Redirect the runner's output directory to a temp dir.
        self._patch = mock.patch("gui.components.runner.RESULTS_DIR", self.tmp)
        self._patch.start()
        # Snapshot the connector registry so we can restore the conftest fakes
        # after this test class is done — restore_real_connectors() would
        # roll back to import-time state and break sibling tests.
        self._snapshot = dict(llm_factory_connector.MODEL_PROVIDER_MAP)
        fakes.install_demo_connector()

    def tearDown(self) -> None:
        self._patch.stop()
        llm_factory_connector.MODEL_PROVIDER_MAP.clear()
        llm_factory_connector.MODEL_PROVIDER_MAP.update(self._snapshot)
        fakes._DEMO_INSTALLED = False
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_run_config_writes_expected_files(self) -> None:
        config = by_key("pd_classic").load()
        config["name"] = "runner test"
        outcome = run_config(config, display_name="runner test")
        self.assertTrue((outcome.output_dir / "config.json").is_file())
        self.assertTrue((outcome.output_dir / "results.csv").is_file())
        self.assertTrue((outcome.output_dir / "raw_results.json").is_file())
        self.assertGreater(outcome.df.shape[0], 0)

    def test_list_and_load_past_runs_round_trip(self) -> None:
        config = by_key("pd_tournament").load()
        first = run_config(config, display_name="t1")
        runs = list_past_runs()
        self.assertIn(first.output_dir, runs)
        reloaded = load_past_run(first.output_dir)
        self.assertEqual(reloaded.df.shape, first.df.shape)

    def test_runs_listed_newest_first(self) -> None:
        # Two runs with deliberate sleep between to ensure distinct timestamps.
        import time

        run_config(by_key("pd_classic").load(), display_name="alpha")
        time.sleep(1.1)
        run_config(by_key("pd_classic").load(), display_name="beta")
        runs = list_past_runs()
        # First entry must have a later mtime / lexicographic name than the
        # second (we sort by name reverse, with timestamp prefix).
        self.assertGreaterEqual(runs[0].name, runs[1].name)

    def test_run_directory_naming_uses_timestamp_prefix(self) -> None:
        outcome = run_config(by_key("pd_classic").load(), display_name="ts test")
        # Expect YYYYMMDD_HHMMSS_<slug> at the start of the directory name.
        parts = outcome.output_dir.name.split("_")
        self.assertGreaterEqual(len(parts), 3)
        self.assertEqual(len(parts[0]), 8)  # YYYYMMDD
        self.assertEqual(len(parts[1]), 6)  # HHMMSS

    def test_persisted_config_round_trips_through_load(self) -> None:
        config = by_key("pd_classic").load()
        config["name"] = "config round trip"
        outcome = run_config(config, display_name="round trip")
        reloaded = load_past_run(outcome.output_dir)
        self.assertEqual(reloaded.config["name"], config["name"])


# ---------------------------------------------------------------------------
# Plot helpers — happy paths
# ---------------------------------------------------------------------------

class TestPlotsRender(unittest.TestCase):
    """Plot helpers should produce a Plotly Figure for valid inputs."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="fg_plots_"))
        self._patch = mock.patch("gui.components.runner.RESULTS_DIR", self.tmp)
        self._patch.start()
        self._snapshot = dict(llm_factory_connector.MODEL_PROVIDER_MAP)
        fakes.install_demo_connector()

    def tearDown(self) -> None:
        self._patch.stop()
        llm_factory_connector.MODEL_PROVIDER_MAP.clear()
        llm_factory_connector.MODEL_PROVIDER_MAP.update(self._snapshot)
        fakes._DEMO_INSTALLED = False
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_cooperation_rate_returns_figure_for_real_run(self) -> None:
        outcome = run_config(by_key("pd_classic").load(), display_name="plot")
        fig = cooperation_rate_per_round(outcome.raw)
        self.assertIsNotNone(fig)
        # Plotly Figure has data.
        self.assertGreater(len(fig.data), 0)

    def test_score_per_round_returns_figure_for_real_run(self) -> None:
        outcome = run_config(by_key("pd_classic").load(), display_name="plot")
        fig = score_per_round(outcome.raw)
        self.assertIsNotNone(fig)


if __name__ == "__main__":
    unittest.main()
