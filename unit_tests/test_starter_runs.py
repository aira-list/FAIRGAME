"""Starter-run seeding: shipped sample runs are copied into RUNS_DIR at startup.

``starter_library/runs/`` holds real engine output (see
``tools/populate_seed_results.py``); ``seed_starter_runs`` tops missing run
ids up into ``RUNS_DIR`` so a fresh install has results to visualise.
"""

from __future__ import annotations

import json
import unittest

from unit_tests.support import isolated_storage_dirs
from web_api.run_history import STARTER_RUNS_DIR, list_runs, load_run, seed_starter_runs


@unittest.skipUnless(STARTER_RUNS_DIR.is_dir(), "starter_library/runs absent")
class TestStarterRunSeeding(unittest.TestCase):
    def test_seeds_into_empty_runs_dir(self) -> None:
        with isolated_storage_dirs(data=False) as dirs:
            seed_starter_runs()
            shipped = {p.name for p in STARTER_RUNS_DIR.iterdir() if (p / "metadata.json").is_file()}
            copied = {p.name for p in dirs["runs"].iterdir()}
            self.assertEqual(copied, shipped)
            # Listed + loadable through the normal read path.
            metas = list_runs()
            self.assertEqual(len(metas), len(shipped))
            run = load_run(metas[0]["id"])
            self.assertGreater(len(run["rows"]), 0)

    def test_topup_never_overwrites_existing_run(self) -> None:
        with isolated_storage_dirs(data=False) as dirs:
            seed_starter_runs()
            some_id = next(iter(p.name for p in dirs["runs"].iterdir()))
            marker = dirs["runs"] / some_id / "metadata.json"
            meta = json.loads(marker.read_text())
            meta["name"] = "user-edited"
            marker.write_text(json.dumps(meta))
            seed_starter_runs()  # second pass must not clobber the edit
            self.assertEqual(json.loads(marker.read_text())["name"], "user-edited")

    def test_shipped_runs_reference_seed_configurations(self) -> None:
        for p in STARTER_RUNS_DIR.iterdir():
            meta_file = p / "metadata.json"
            if not meta_file.is_file():
                continue
            meta = json.loads(meta_file.read_text())
            self.assertTrue(
                str(meta.get("configuration_id", "")).startswith("seed_cfg_"),
                f"{p.name} is not linked to a seed configuration",
            )
