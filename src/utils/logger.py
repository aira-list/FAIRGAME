"""Centralized logging configuration for FAIRGAME.

All modules should obtain their logger via :func:`get_logger`. The first call
to :func:`configure_logging` (typically from an application entry point) sets
up the root logger; subsequent calls are no-ops unless ``force=True``.
"""

from __future__ import annotations

import logging
import os
import sys

_DEFAULT_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_CONFIGURED = False


def configure_logging(
    level: str | None = None,
    fmt: str = _DEFAULT_FORMAT,
    force: bool = False,
) -> None:
    """Configure the root logger for the application.

    Args:
        level: Log level name (DEBUG, INFO, WARNING, ERROR). Falls back to the
            ``FAIRGAME_LOG_LEVEL`` env var, then ``INFO``.
        fmt: ``logging.Formatter`` format string.
        force: When ``True``, reconfigures even if already configured.
    """
    global _CONFIGURED
    if _CONFIGURED and not force:
        return

    raw_level = level or os.getenv("FAIRGAME_LOG_LEVEL") or "INFO"
    resolved_level = raw_level.upper()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt))

    root = logging.getLogger()
    if force:
        root.handlers.clear()
    root.setLevel(resolved_level)
    root.addHandler(handler)

    # Quiet noisy third-party loggers we don't own.
    for noisy in ("urllib3", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger, configuring the root logger lazily."""
    if not _CONFIGURED:
        configure_logging()
    return logging.getLogger(name)
