"""Backwards-compatibility shim for the unified connector module.

Historically this module contained an HTTP client to a separate ``llmfactory``
microservice, gated by ``OPEN_SOURCE_FLAG``. The shim now re-exports the
in-process implementation from :mod:`src.llm_connectors.llm_factory_connector`
so older imports keep working while emitting a ``DeprecationWarning``.
"""

from __future__ import annotations

import warnings

from src.llm_connectors.llm_factory_connector import (  # noqa: F401  re-export
    ChatModelFactory,
    MODEL_PROVIDER_MAP,
    execute_prompt,
    register_model,
)

warnings.warn(
    "src.llm_factory_connector is deprecated; import from "
    "src.llm_connectors instead.",
    DeprecationWarning,
    stacklevel=2,
)
