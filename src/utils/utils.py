import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import overload

from src.utils.logger import get_logger

logger = get_logger(__name__)


def get_project_root(path: Path, levels_up) -> Path:
    if levels_up < 0:
        raise ValueError(f"levels_up must be non-negative, got {levels_up}.")
    # ``Path.parent`` saturates at the filesystem root, so an over-count
    # silently returned ``/`` instead of failing. Reject it explicitly.
    if levels_up > len(path.parents):
        raise ValueError(
            f"levels_up={levels_up} exceeds the depth of {path} ({len(path.parents)} ancestors)."
        )
    for _ in range(levels_up):
        path = path.parent
    return path


def get_resources_dir() -> Path:
    """Location of the paper's ``resources/`` folder (example configs + templates).

    This material was moved out of the app into the sibling
    ``Fairgame_paper_evaluations`` project. The web app no longer depends on it,
    but CLI / generator / test tooling still reads from here. Override the
    location with the ``FAIRGAME_RESOURCES_DIR`` environment variable.
    """
    override = os.getenv("FAIRGAME_RESOURCES_DIR")
    if override:
        return Path(override)
    project_root = get_project_root(Path(__file__).resolve(), 3)
    return project_root.parent / "Fairgame_paper_evaluations" / "resources"


# utils.py or text_utils.py
def round_index(round_key) -> int:
    """Parse the numeric index ``n`` from a ``round_<n>`` history key.

    Shared by the history-ordering call sites (``GameHistory.describe`` and
    ``PromptCreator``) that previously each re-implemented
    ``int(key.split("_")[1])`` with subtly different error handling.
    """
    return int(str(round_key).split("_")[1])


def slug(text: str) -> str:
    """Convert text to URL-safe slug format."""
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")


def _env[T: (int, float)](name: str, cast: Callable[[str], T], default: T | None) -> T | None:
    """Read env var ``name`` and cast it, falling back to ``default``.

    Returns ``default`` when the variable is unset, empty, or fails to parse
    (a parse failure is logged). Shared by the LLM connectors so tuning knobs
    like ``FAIRGAME_LLM_*`` are read with one consistent, forgiving policy.
    """
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return cast(raw)
    except ValueError:
        logger.warning("Invalid value for %s=%r; using %r.", name, raw, default)
        return default


@overload
def int_env(name: str, default: int) -> int: ...
@overload
def int_env(name: str, default: None = ...) -> int | None: ...
def int_env(name: str, default: int | None = None) -> int | None:
    """Integer env var, or ``default`` if unset/empty/invalid."""
    return _env(name, int, default)


@overload
def float_env(name: str, default: float) -> float: ...
@overload
def float_env(name: str, default: None = ...) -> float | None: ...
def float_env(name: str, default: float | None = None) -> float | None:
    """Float env var, or ``default`` if unset/empty/invalid."""
    return _env(name, float, default)
