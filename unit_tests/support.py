"""Shared test-support helpers.

Importable by any test module (``from unit_tests.support import ...``); kept
out of ``conftest.py`` so the helpers can be imported explicitly rather than
appearing by fixture magic.
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from web_api import storage


@contextmanager
def isolated_storage_dirs(
    *, data: bool = True, runs: bool = True, prefix: str = "fg_test_"
) -> Iterator[dict[str, Path]]:
    """Redirect ``storage.DATA_DIR`` / ``storage.RUNS_DIR`` at fresh tempdirs.

    The single sanctioned way to isolate a test from the developer's real
    library and run history — hand-rolled per-file variants of this swap
    repeatedly drifted (one forgot DATA_DIR and silently depended on the
    live library). Yields ``{"data": Path, "runs": Path}`` for whichever
    dirs were redirected; everything is restored and removed on exit even
    when the test body raises.
    """
    real_data, real_runs = storage.DATA_DIR, storage.RUNS_DIR
    out: dict[str, Path] = {}
    try:
        if data:
            out["data"] = Path(tempfile.mkdtemp(prefix=prefix + "data_"))
            storage.DATA_DIR = out["data"]
        if runs:
            out["runs"] = Path(tempfile.mkdtemp(prefix=prefix + "runs_"))
            storage.RUNS_DIR = out["runs"]
        yield out
    finally:
        storage.DATA_DIR = real_data
        storage.RUNS_DIR = real_runs
        for path in out.values():
            shutil.rmtree(path, ignore_errors=True)


def canonical_pd_matrix(*, labels: dict[str, str] | None = None, language: str = "en") -> dict:
    """The canonical 2x2 Prisoner's Dilemma payoff matrix (T=5 > R=3 > P=1 > S=0).

    One shared fixture instead of the same literal copy-pasted (with subtly
    different magic weights) across test files. ``labels`` overrides the
    display labels, e.g. ``{"strategy1": "Coop", "strategy2": "Defect"}``.
    """
    return {
        "weights": {"weight1": 3, "weight2": 5, "weight3": 0, "weight4": 1},
        "strategies": {language: dict(labels or {"strategy1": "Cooperate", "strategy2": "Defect"})},
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
    }
