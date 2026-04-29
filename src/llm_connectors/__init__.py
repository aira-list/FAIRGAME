"""LLM provider connectors and the registry that selects between them.

The factory module is imported lazily so that environments without a given
provider SDK installed (for example in lightweight test runs) can still load
:mod:`src.llm_connectors`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.llm_connectors.abstract_connector import AbstractConnector

__all__ = [
    "AbstractConnector",
    "ChatModelFactory",
    "MODEL_PROVIDER_MAP",
    "execute_prompt",
    "register_model",
]


def __getattr__(name):  # noqa: D401 - module dunder
    if name in {"ChatModelFactory", "MODEL_PROVIDER_MAP", "execute_prompt", "register_model"}:
        from src.llm_connectors import llm_factory_connector as factory  # noqa: WPS433

        return getattr(factory, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if TYPE_CHECKING:  # pragma: no cover
    from src.llm_connectors.llm_factory_connector import (  # noqa: F401
        ChatModelFactory,
        MODEL_PROVIDER_MAP,
        execute_prompt,
        register_model,
    )
