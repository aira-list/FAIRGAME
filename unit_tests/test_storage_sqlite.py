"""Tests for the SQLite-backed library store (web_api.storage).

Covers the behaviours the JSON-file store guaranteed and that callers depend
on: round-trip + stable ordering, concurrent read-modify-write through
``edit_store`` with no lost updates, tombstone survival across a reload,
one-time migration from legacy ``data/<name>.json`` files, and full isolation
when ``DATA_DIR`` is monkey-patched at a tempdir.
"""

from __future__ import annotations

import json
import threading
import unittest
from contextlib import contextmanager

from unit_tests.support import isolated_storage_dirs
from web_api import storage


@contextmanager
def _TmpDataDir():
    """DATA_DIR-only isolation (thin alias over the shared helper)."""
    with isolated_storage_dirs(runs=False, prefix="fg_sqlite_") as dirs:
        yield dirs["data"]


class TestRoundTrip(unittest.TestCase):
    def test_save_load_preserves_items_and_order(self) -> None:
        with _TmpDataDir():
            items = [{"id": "a", "n": 1}, {"id": "b", "n": 2}, {"id": "c", "n": 3}]
            storage.save_store("things", items)
            self.assertEqual(storage.load_store("things"), items)

    def test_overwrite_replaces_whole_store(self) -> None:
        with _TmpDataDir():
            storage.save_store("things", [{"id": "old"}])
            storage.save_store("things", [{"id": "new1"}, {"id": "new2"}])
            self.assertEqual([i["id"] for i in storage.load_store("things")], ["new1", "new2"])

    def test_creates_sqlite_db_file(self) -> None:
        with _TmpDataDir() as d:
            storage.save_store("things", [{"id": "x"}])
            self.assertTrue((d / "library.db").is_file())

    def test_sqlite_is_the_only_write_path(self) -> None:
        # SQLite is the single source of truth: saving must NOT write a
        # parallel JSON snapshot (the legacy layout is read-only, for
        # migration only).
        with _TmpDataDir() as d:
            storage.save_store("things", [{"id": "a"}, {"id": "b"}])
            self.assertFalse((d / "things.json").exists())


class TestConcurrentEditStore(unittest.TestCase):
    def test_parallel_edits_never_lose_updates(self) -> None:
        with _TmpDataDir():
            storage.save_store("things", [])
            per_thread = 10
            n_threads = 8
            errors: list = []

            def worker(w: int) -> None:
                try:
                    for i in range(per_thread):
                        with storage.edit_store("things") as items:
                            items.append({"id": f"{w}-{i}"})
                except Exception as exc:  # noqa: BLE001
                    errors.append(exc)

            threads = [threading.Thread(target=worker, args=(w,)) for w in range(n_threads)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.assertEqual(errors, [], f"edit_store errors: {errors[:3]}")
            got = storage.load_store("things")
            self.assertEqual(len(got), per_thread * n_threads)
            # Every appended id is present exactly once (no lost / duplicated writes).
            ids = [i["id"] for i in got]
            self.assertEqual(len(set(ids)), len(ids))


class TestRollbackOnError(unittest.TestCase):
    def test_exception_in_edit_store_leaves_store_untouched(self) -> None:
        with _TmpDataDir():
            storage.save_store("things", [{"id": "keep"}])
            with self.assertRaises(RuntimeError), storage.edit_store("things") as items:
                items.append({"id": "transient"})
                raise RuntimeError("boom")
            self.assertEqual([i["id"] for i in storage.load_store("things")], ["keep"])


class TestTombstones(unittest.TestCase):
    def test_deleted_seed_id_stays_deleted_across_reload(self) -> None:
        with _TmpDataDir():
            # Fresh load seeds the starter library; gt_pd is a shipped seed.
            seeded = {t["id"] for t in storage.load_store("game_types")}
            self.assertIn("gt_pd", seeded)

            with storage.edit_store("game_types") as items:
                items[:] = [it for it in items if it["id"] != "gt_pd"]
            storage.record_deletion("game_types", "gt_pd")

            # Reload: top-up must NOT resurrect the tombstoned seed.
            after = {t["id"] for t in storage.load_store("game_types")}
            self.assertNotIn("gt_pd", after)


class TestMigration(unittest.TestCase):
    def test_legacy_json_imported_on_first_use(self) -> None:
        with _TmpDataDir() as d:
            legacy = [{"id": "legacy1", "name": "L1"}, {"id": "legacy2", "name": "L2"}]
            (d / "game_types.json").write_text(json.dumps(legacy))
            self.assertFalse((d / "library.db").exists())

            ids = {t["id"] for t in storage.load_store("game_types")}
            self.assertTrue((d / "library.db").is_file())
            # Legacy rows survived the migration (seed top-up may add more).
            self.assertIn("legacy1", ids)
            self.assertIn("legacy2", ids)

    def test_legacy_json_preserved_for_unseeded_store(self) -> None:
        with _TmpDataDir() as d:
            legacy = [{"id": "x", "v": 1}, {"id": "y", "v": 2}]
            (d / "things.json").write_text(json.dumps(legacy))
            self.assertEqual(storage.load_store("things"), legacy)
            # Legacy file left in place (not deleted).
            self.assertTrue((d / "things.json").is_file())

    def test_no_migration_when_db_already_exists(self) -> None:
        with _TmpDataDir() as d:
            # DB created first, store empty.
            storage.save_store("things", [])
            self.assertTrue((d / "library.db").exists())
            # A legacy file dropped in afterwards must NOT be imported.
            (d / "things.json").write_text(json.dumps([{"id": "late"}]))
            self.assertEqual(storage.load_store("things"), [])

    def test_legacy_tombstone_sidecar_imported_on_first_use(self) -> None:
        # Pre-SQLite installs kept tombstones in *.tombstones.json sidecars;
        # they must migrate into the DB so deleted seeds stay deleted.
        with _TmpDataDir() as d:
            (d / "game_types.tombstones.json").write_text(json.dumps(["gt_pd"]))
            ids = {t["id"] for t in storage.load_store("game_types")}
            self.assertNotIn("gt_pd", ids)  # seed suppressed by migrated tombstone
            self.assertTrue(len(ids) > 0)  # other seeds still arrive


class TestIsolation(unittest.TestCase):
    def test_monkeypatched_data_dir_isolates_stores(self) -> None:
        with _TmpDataDir():
            storage.save_store("things", [{"id": "a"}])
            self.assertEqual([i["id"] for i in storage.load_store("things")], ["a"])
        # A different tempdir is a completely independent database.
        with _TmpDataDir():
            self.assertEqual(storage.load_store("things"), [])


if __name__ == "__main__":
    unittest.main()
