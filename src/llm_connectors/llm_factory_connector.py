"""Single entry point for selecting and invoking LLM provider connectors.

Provider connector classes are imported lazily via thin loader callables so a
missing SDK (e.g. ``mistralai`` not installed) only fails when that specific
model is used, not when the module is imported.
"""

from __future__ import annotations

from typing import Callable, Dict, Tuple, Type

from dotenv import load_dotenv

from src.llm_connectors.abstract_connector import AbstractConnector
from src.utils.logger import get_logger

load_dotenv()

logger = get_logger(__name__)


def _load_openai() -> Type[AbstractConnector]:
    from src.llm_connectors.openai_connector import OpenAIConnector

    return OpenAIConnector


def _load_anthropic() -> Type[AbstractConnector]:
    from src.llm_connectors.anthropic_connector import AnthropicConnector

    return AnthropicConnector


def _load_mistral() -> Type[AbstractConnector]:
    from src.llm_connectors.mistral_connector import MistralConnector

    return MistralConnector


# Map abstract names -> (lazy-loader callable, provider model id).
ProviderEntry = Tuple[Callable[[], Type[AbstractConnector]], str]

MODEL_PROVIDER_MAP: Dict[str, ProviderEntry] = {
    "Claude35Sonnet": (_load_anthropic, "claude-3-5-sonnet-20241022"),
    "Claude4Sonnet": (_load_anthropic, "claude-sonnet-4-5"),
    "MistralLarge": (_load_mistral, "mistral-large-latest"),
    "OpenAIGPT4o": (_load_openai, "gpt-4o"),
    "OpenAIGPT4oMini": (_load_openai, "gpt-4o-mini"),
}


def register_model(
    name: str,
    connector_cls: Type[AbstractConnector],
    provider_model: str,
) -> None:
    """Register (or override) a logical model name. Useful in tests."""
    MODEL_PROVIDER_MAP[name] = (lambda cls=connector_cls: cls, provider_model)
    logger.debug(
        "Registered model %r -> %s/%s",
        name,
        connector_cls.__name__,
        provider_model,
    )


class ChatModelFactory:
    """Resolve a logical model name to an instantiated connector."""

    @staticmethod
    def get_model(model_name: str) -> AbstractConnector:
        provider_info = MODEL_PROVIDER_MAP.get(model_name)
        if not provider_info:
            raise ValueError(
                f"Unsupported model {model_name!r}. "
                f"Known models: {sorted(MODEL_PROVIDER_MAP)}"
            )
        loader, provider_model = provider_info
        connector_cls = loader()
        return connector_cls(provider_model)


def execute_prompt(model_name: str, prompt: str) -> str:
    """Execute ``prompt`` using the connector registered for ``model_name``."""
    chat_model = ChatModelFactory.get_model(model_name)
    return chat_model.send_prompt(prompt)


if __name__ == "__main__":  # pragma: no cover - CLI surface
    import sys

    model_id = sys.argv[1] if len(sys.argv) > 1 else "OpenAIGPT4o"
    prompt_text = sys.argv[2] if len(sys.argv) > 2 else "Tell me a programming joke."
    try:
        print(execute_prompt(model_id, prompt_text))
    except Exception as exc:  # noqa: BLE001
        logger.error("Prompt execution failed: %s", exc)
        sys.exit(1)
