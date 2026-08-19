"""Run persistence keeps result rows in their native JSON shape.

Regression guard for the results-row contract: a saved-then-reloaded run must
return the SAME shape the ``/run`` endpoint returns live — list cells are real
lists, not the Python-repr strings the old CSV-only round-trip produced. Also
checks the legacy CSV fallback still loads runs written before ``rows.json``.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from web_api import run_history, storage


class TestRunPersistenceRoundTrip(unittest.TestCase):
    def setUp(self) -> None:
        self._real = storage.RUNS_DIR
        self._tmp = Path(tempfile.mkdtemp(prefix="fg_runpersist_"))
        storage.RUNS_DIR = self._tmp

    def tearDown(self) -> None:
        storage.RUNS_DIR = self._real
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _rows(self):
        return [
            {
                "game_id": "game_0",
                "language": "en",
                "played_rounds": 2,
                "agent1_strategies": ["Cooperate", "Defect"],  # list cell
                "agent1_scores": [3.0, 1.0],  # list cell
                "agent1_messages": [],
                "welfare_sum": 8.0,  # scalar
            }
        ]

    def test_saved_rows_reload_with_native_types(self) -> None:
        run_history.save_run("run_native", {"name": "t"}, self._rows())
        loaded = run_history.load_run("run_native")["rows"]

        self.assertEqual(loaded, self._rows())  # value-equal
        cell = loaded[0]["agent1_strategies"]
        self.assertIsInstance(cell, list, "list cell must reload as a real list")
        self.assertEqual(cell, ["Cooperate", "Defect"])
        self.assertIsInstance(loaded[0]["welfare_sum"], float)

    def test_rows_json_is_the_canonical_store(self) -> None:
        run_dir = run_history.save_run("run_files", {"name": "t"}, self._rows())
        self.assertTrue((run_dir / "rows.json").is_file())
        self.assertTrue((run_dir / "results.csv").is_file(), "CSV export still written")
        on_disk = json.loads((run_dir / "rows.json").read_text())
        self.assertEqual(on_disk[0]["agent1_scores"], [3.0, 1.0])

    def test_legacy_csv_only_run_still_loads(self) -> None:
        # Simulate a pre-rows.json run: metadata.json + results.csv only, with
        # list cells written as their repr string (the old CSV shape).
        run_dir = self._tmp / "legacy"
        run_dir.mkdir()
        (run_dir / "metadata.json").write_text(json.dumps({"id": "legacy", "name": "old"}))
        pd.DataFrame(self._rows()).to_csv(run_dir / "results.csv", index=False)

        loaded = run_history.load_run("legacy")["rows"]
        self.assertEqual(loaded[0]["game_id"], "game_0")
        # The dashboard parser tolerates the repr-string list cell.
        from web_api.dashboards import as_list

        self.assertEqual(as_list(loaded[0]["agent1_strategies"]), ["Cooperate", "Defect"])


if __name__ == "__main__":
    unittest.main()
