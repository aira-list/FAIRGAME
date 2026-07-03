"""Filesystem paths + SQLite-backed store for the user library.

The user-managed library (game types / templates / configurations) is backed
by a single SQLite database at ``data/library.db`` — the one and only source
of truth. Each *store* is a flat list of dicts (each with an ``id``); a store
maps to the rows of the shared ``library`` table whose ``store`` column
matches its name, ordered by an autoincrement ``seq`` so insertion order is
stable. Tombstones (ids of seed entries the user deleted, which the seed
top-up must never resurrect) live in the ``tombstones`` table of the same
database.

Migration from the historical layouts happens once, when ``library.db`` is
first created: legacy ``data/<name>.json`` stores and ``*.tombstones.json``
sidecars are imported and then left in place (read-only relics; nothing
writes them anymore).

Public surface for callers (routes, tools, tests): :func:`load_store`,
:func:`edit_store`, :func:`save_store`, :func:`record_deletion`,
:func:`new_id`, :func:`now_iso`, the path helpers, and the path constants —
exposed on the module so tests can monkey-patch them. The database path is
derived from ``DATA_DIR`` at call time, so redirecting ``DATA_DIR`` at a
tempdir fully isolates a test's library.
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from src.utils.logger import get_logger
from src.utils.utils import get_resources_dir

logger = get_logger(__name__)

# Serializes library-store access. FastAPI runs sync handlers in a threadpool,
# so concurrent requests can otherwise interleave load→mutate→save. Re-entrant
# so ``load_store`` may call ``save_store`` (seed top-up) while holding it.
_STORE_LOCK = threading.RLock()

# A single safe path segment (run ids, config ids): no separators, no
# traversal. Used as defense-in-depth alongside ``resolve_within`` below.
_SAFE_SEGMENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def is_safe_segment(value: str) -> bool:
    """True if ``value`` is a single safe path segment (no ``/``, ``..``)."""
    return bool(value) and value not in {".", ".."} and bool(_SAFE_SEGMENT_RE.fullmatch(value))


def resolve_within(base: Path, *parts: str) -> Path | None:
    """Resolve ``base / parts`` and return it only if it stays inside ``base``.

    Returns ``None`` on any traversal / escape (``..``, absolute paths,
    symlinks pointing outside). The containment check is done on the
    *resolved* paths so lexical guards (``base in target.parents`` on an
    unresolved path) can't be bypassed.
    """
    base_resolved = base.resolve()
    try:
        candidate = (base / Path(*parts)).resolve()
    except (ValueError, OSError):
        return None
    if candidate == base_resolved or base_resolved in candidate.parents:
        return candidate
    return None


PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = PROJECT_ROOT / "web"
# The paper's resources/ moved to the sibling Fairgame_paper_evaluations project.
# The web app no longer reads it; this alias is kept for tooling/tests that do.
RESOURCES_DIR = get_resources_dir()
RUNS_DIR = PROJECT_ROOT / "results" / "web"
DATA_DIR = PROJECT_ROOT / "data"

RUNS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)


def legacy_store_path(name: str) -> Path:
    """Path of the pre-SQLite ``data/<name>.json`` store (migration source)."""
    return DATA_DIR / f"{name}.json"


def _db_path() -> Path:
    """SQLite file backing the library, derived from ``DATA_DIR`` at call time.

    Resolved lazily so tests that monkey-patch ``DATA_DIR`` get an isolated
    database under their tempdir.
    """
    return DATA_DIR / "library.db"


def _seed_data(name: str) -> list[dict[str, Any]]:
    """Initial game types / templates / configurations for a fresh install.

    Returned (and persisted) when store ``name`` is missing or empty so a new
    user lands on a usable library.
    """
    from web_api import seeds  # local import: seeds → storage might cycle

    if name == "game_types":
        return list(seeds.SEED_GAME_TYPES)
    if name == "templates":
        return list(seeds.SEED_TEMPLATES)
    if name == "configurations":
        return list(seeds.SEED_CONFIGURATIONS)
    return []


# ---- SQLite backend -----------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS library (
    seq     INTEGER PRIMARY KEY AUTOINCREMENT,
    store   TEXT NOT NULL,
    item_id TEXT,
    data    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_library_store_seq ON library(store, seq);
CREATE TABLE IF NOT EXISTS tombstones (
    store   TEXT NOT NULL,
    item_id TEXT NOT NULL,
    PRIMARY KEY (store, item_id)
);
"""


@contextmanager
def _db() -> Iterator[sqlite3.Connection]:
    """Open the library database (creating + migrating it on first use).

    A fresh database whose sibling legacy ``data/<name>.json`` files exist is
    seeded from them (one-time migration). Always called under ``_STORE_LOCK``.
    ``check_same_thread=False`` because FastAPI dispatches sync handlers across
    a threadpool; the lock (not the connection) provides the mutual exclusion.
    """
    path = _db_path()
    needs_migration = not path.exists()
    conn = sqlite3.connect(str(path), check_same_thread=False)
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
        if needs_migration:
            _import_legacy_json(conn)
        yield conn
    finally:
        conn.close()


def _write_rows(conn: sqlite3.Connection, name: str, items: list[dict[str, Any]]) -> None:
    """Replace all rows of store ``name`` with ``items`` (in list order).

    Runs inside a transaction so a mid-write error rolls the store back to its
    previous contents rather than leaving it half-replaced.
    """
    with conn:  # atomic: commit on success, rollback on exception
        conn.execute("DELETE FROM library WHERE store = ?", (name,))
        conn.executemany(
            "INSERT INTO library (store, item_id, data) VALUES (?, ?, ?)",
            [
                (
                    name,
                    item.get("id") if isinstance(item, dict) else None,
                    json.dumps(item),
                )
                for item in items
            ],
        )


def _import_legacy_json(conn: sqlite3.Connection) -> None:
    """One-time migration: import the legacy JSON layout into the database.

    Runs only when the database file did not previously exist. Both the
    ``data/<name>.json`` stores and the ``data/<name>.tombstones.json``
    sidecars are imported; the files are left in place as read-only relics.
    """
    for path in sorted(DATA_DIR.glob("*.json")):
        try:
            items = json.loads(path.read_text())
        except (ValueError, OSError):
            continue
        if not isinstance(items, list) or not items:
            continue
        if path.name.endswith(".tombstones.json"):
            store = path.name[: -len(".tombstones.json")]
            with conn:
                conn.executemany(
                    "INSERT OR IGNORE INTO tombstones (store, item_id) VALUES (?, ?)",
                    [(store, str(i)) for i in items],
                )
            logger.info("Migrated legacy tombstones for %s (%d ids).", store, len(items))
        else:
            _write_rows(conn, path.stem, items)
            logger.info(
                "Migrated legacy store %s (%d items) into %s.",
                path.name,
                len(items),
                _db_path().name,
            )


# ---- Public store API -----------------------------------------------------


def load_store(name: str) -> list[dict[str, Any]]:
    with _STORE_LOCK:
        return _load_store_locked(name)


@contextmanager
def edit_store(name: str) -> Iterator[list[dict[str, Any]]]:
    """Load a store for read-modify-write under the store lock.

    The yielded list is saved back on clean exit; an exception (e.g. an
    HTTPException raised mid-mutation) leaves the store untouched. Handlers
    must use this — a bare ``load_store``/mutate/``save_store`` sequence
    releases the lock in between and loses concurrent writes.
    """
    with _STORE_LOCK:
        items = _load_store_locked(name)
        yield items
        save_store(name, items)


def _load_store_locked(name: str) -> list[dict[str, Any]]:
    with _db() as conn:
        rows = conn.execute(
            "SELECT data FROM library WHERE store = ? ORDER BY seq", (name,)
        ).fetchall()
        tombstones = _load_tombstones(conn, name)
    items: list[dict[str, Any]] = []
    for (blob,) in rows:
        try:
            items.append(json.loads(blob))
        except (ValueError, TypeError):
            logger.warning("Skipping unparsable row in store %s.", name)
    # Top-up: append any seed entries whose id is missing (this also covers the
    # fresh-install / empty-store case). Existing user edits are untouched (we
    # never overwrite an id that's already present) and ids the user explicitly
    # deleted stay deleted (tombstones). Lets us ship new translations / new
    # sample configurations without forcing users to wipe their library.
    seed = _seed_data(name)
    if seed:
        existing_ids = {it.get("id") for it in items}
        added = [
            s
            for s in seed
            if s.get("id") and s["id"] not in existing_ids and s["id"] not in tombstones
        ]
        if added:
            items.extend(added)
            save_store(name, items)
            logger.info("Added %d new seed entries to %s.", len(added), name)
    return items


def save_store(name: str, items: list[dict[str, Any]]) -> None:
    with _STORE_LOCK, _db() as conn:
        _write_rows(conn, name, items)


def _load_tombstones(conn: sqlite3.Connection, name: str) -> set[str]:
    """Ids of seed entries the user deleted — never re-added by top-up."""
    rows = conn.execute("SELECT item_id FROM tombstones WHERE store = ?", (name,)).fetchall()
    return {r[0] for r in rows}


def record_deletion(name: str, item_id: str) -> None:
    """Remember that ``item_id`` was deleted from store ``name``.

    Without this, deleting a starter-library item is silently undone by the
    seed top-up on the very next load. Non-seed ids are recorded too; they
    are harmless (top-up only consults seed ids).
    """
    with _STORE_LOCK, _db() as conn, conn:
        conn.execute(
            "INSERT OR IGNORE INTO tombstones (store, item_id) VALUES (?, ?)",
            (name, item_id),
        )


def newest_first(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Display order for library lists: user items newest-first, then the
    shipped seed entries (no ``created_at``) in their curated store order.

    Ordering is derived from ``created_at`` at read time — never from the
    store's physical row order, which multiple writers (creates, clones,
    imports, the seed top-up) would each have to maintain by hand.
    """
    stamped = [i for i in items if i.get("created_at")]
    rest = [i for i in items if not i.get("created_at")]
    return sorted(stamped, key=lambda i: str(i["created_at"]), reverse=True) + rest


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")
