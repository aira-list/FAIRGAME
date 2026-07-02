"""Single entry point for selecting and invoking LLM provider connectors.

Provider connector classes are imported lazily via thin loader callables so a
missing SDK (e.g. ``mistralai`` not installed) only fails when that specific
model is used, not when the module is imported.
"""

from __future__ import annotations

import contextlib
from contextvars import ContextVar

from dotenv import load_dotenv

from src.llm_connectors.abstract_connector import AbstractConnector
from src.utils.logger import get_logger
from src.utils.utils import float_env, int_env

load_dotenv()

logger = get_logger(__name__)

# Demo mode: when active, every model resolves to the offline DemoConnector so
# scenarios run with no API keys and no provider charges. A ContextVar (not a
# global) keeps it request-scoped and safe under FastAPI's threadpool — the
# value set inside a request propagates through that request's synchronous call
# chain only.
_DEMO_MODE: ContextVar[bool] = ContextVar("fairgame_demo_mode", default=False)


@contextlib.contextmanager
def demo_mode(enabled: bool = True):
    """Within this context, route every LLM call to the offline DemoConnector.

    ``enabled=False`` is a no-op passthrough, so callers can write
    ``with demo_mode(flag):`` unconditionally.
    """
    token = _DEMO_MODE.set(bool(enabled))
    try:
        yield
    finally:
        _DEMO_MODE.reset(token)


def demo_mode_active() -> bool:
    """True if the current context is running in demo mode."""
    return _DEMO_MODE.get()


def _load_litellm() -> type[AbstractConnector]:
    # Imported lazily so ``src.llm_connectors`` loads even where ``litellm``
    # isn't installed (e.g. lightweight test collection).
    from src.llm_connectors.litellm_connector import LiteLLMConnector

    return LiteLLMConnector


# Map logical names -> LiteLLM model string. Every model routes through
# LiteLLM; the string is whatever LiteLLM expects (provider prefix where
# required). Point any name at ``ollama/<model>`` to use a locally-served
# model instead of a hosted provider. Tests can swap the connector class per
# name via :func:`register_model` (see ``_CONNECTOR_OVERRIDES``).
#
# Prefix that lets a config name *any* LiteLLM model string directly,
# bypassing MODEL_PROVIDER_MAP (mirrors the ``baseline:`` convention).
LITELLM_PREFIX = "litellm:"

MODEL_PROVIDER_MAP: dict[str, str] = {
    # ---- Featured models shown in the UI (clean, current names) --------
    # Each needs the matching provider API key in the environment; the exact
    # availability of a given model id depends on your provider account.
    # Anthropic
    "Claude Opus 4.8": "anthropic/claude-opus-4-8",
    "Claude Sonnet 4.6": "anthropic/claude-sonnet-4-6",
    "Claude Haiku 4.5": "anthropic/claude-haiku-4-5",
    "Claude 3.5 Sonnet": "anthropic/claude-3-5-sonnet-latest",
    "Claude 3.5 Haiku": "anthropic/claude-3-5-haiku-latest",
    "Claude 3 Opus": "anthropic/claude-3-opus-latest",
    # OpenAI
    "GPT-4o": "gpt-4o",
    "GPT-4o mini": "gpt-4o-mini",
    "GPT-4.1": "gpt-4.1",
    "GPT-4.1 mini": "gpt-4.1-mini",
    "GPT-4.1 nano": "gpt-4.1-nano",
    "o3": "o3",
    "o3-mini": "o3-mini",
    "o4-mini": "o4-mini",
    "GPT-4 Turbo": "gpt-4-turbo",
    # Google
    "Gemini 2.5 Pro": "gemini/gemini-2.5-pro",
    "Gemini 2.0 Flash": "gemini/gemini-2.0-flash",
    "Gemini 2.0 Flash-Lite": "gemini/gemini-2.0-flash-lite",
    "Gemini 1.5 Pro": "gemini/gemini-1.5-pro",
    "Gemini 1.5 Flash": "gemini/gemini-1.5-flash",
    # Mistral
    "Mistral Large": "mistral/mistral-large-latest",
    "Mistral Small": "mistral/mistral-small-latest",
    "Mistral Nemo": "mistral/open-mistral-nemo",
    "Codestral": "mistral/codestral-latest",
    # DeepSeek
    "DeepSeek V3": "deepseek/deepseek-chat",
    "DeepSeek R1": "deepseek/deepseek-reasoner",
    # xAI
    "Grok 2": "xai/grok-2-latest",
    # Meta Llama (via Groq)
    "Llama 3.3 70B (Groq)": "groq/llama-3.3-70b-versatile",
    "Llama 3.1 8B (Groq)": "groq/llama-3.1-8b-instant",
    # Cohere
    "Command R+": "cohere/command-r-plus",
    "Command R": "cohere/command-r",
    # Local (Ollama) — no API key, requires a running Ollama server
    "Llama 3 (local Ollama)": "ollama/llama3",
    "Mistral (local Ollama)": "ollama/mistral",
    # ---- Legacy logical names — kept resolvable for existing configs,
    #      fixtures and shipped presets, but NOT shown in the UI dropdown.
    "ClaudeOpus": "anthropic/claude-opus-4-8",
    "ClaudeSonnet": "anthropic/claude-sonnet-4-6",
    "ClaudeHaiku": "anthropic/claude-haiku-4-5",
    "Claude35Sonnet": "anthropic/claude-sonnet-4-6",
    "Claude4Sonnet": "anthropic/claude-sonnet-4-6",
    "Claude45Haiku": "anthropic/claude-haiku-4-5",
    "MistralLarge": "mistral/mistral-large-latest",
    "OpenAIGPT4o": "gpt-4o",
    "OpenAIGPT4oMini": "gpt-4o-mini",
    "DeepseekV3": "deepseek/deepseek-chat",
    # Any other model: name it ``litellm:<model>`` (see LITELLM_PREFIX),
    # including locally-served ones via ``litellm:ollama/<model>``.
}

# Per-name connector-class overrides — the extension seam ``register_model``
# fills (the offline test suite plugs its deterministic fake in here).
# Absent an override, every model uses the LiteLLM connector.
_CONNECTOR_OVERRIDES: dict[str, type[AbstractConnector]] = {}

# The ordered, curated set surfaced in the UI dropdown (newest/most useful
# first). Legacy aliases above are intentionally excluded so the picker shows
# clean, current names rather than internal tags.
FEATURED_MODELS: list[str] = [
    # Anthropic
    "Claude Opus 4.8",
    "Claude Sonnet 4.6",
    "Claude Haiku 4.5",
    "Claude 3.5 Sonnet",
    "Claude 3.5 Haiku",
    "Claude 3 Opus",
    # OpenAI
    "GPT-4o",
    "GPT-4o mini",
    "GPT-4.1",
    "GPT-4.1 mini",
    "GPT-4.1 nano",
    "o3",
    "o3-mini",
    "o4-mini",
    "GPT-4 Turbo",
    # Google
    "Gemini 2.5 Pro",
    "Gemini 2.0 Flash",
    "Gemini 2.0 Flash-Lite",
    "Gemini 1.5 Pro",
    "Gemini 1.5 Flash",
    # Mistral
    "Mistral Large",
    "Mistral Small",
    "Mistral Nemo",
    "Codestral",
    # DeepSeek
    "DeepSeek V3",
    "DeepSeek R1",
    # xAI
    "Grok 2",
    # Meta Llama (via Groq)
    "Llama 3.3 70B (Groq)",
    "Llama 3.1 8B (Groq)",
    # Cohere
    "Command R+",
    "Command R",
    # Local (Ollama)
    "Llama 3 (local Ollama)",
    "Mistral (local Ollama)",
]


def register_model(
    name: str,
    connector_cls: type[AbstractConnector],
    provider_model: str,
) -> None:
    """Register (or override) a logical model name. Useful in tests."""
    MODEL_PROVIDER_MAP[name] = provider_model
    _CONNECTOR_OVERRIDES[name] = connector_cls
    logger.debug(
        "Registered model %r -> %s/%s",
        name,
        connector_cls.__name__,
        provider_model,
    )


class ChatModelFactory:
    """Resolve a logical model name to an instantiated connector."""

    @staticmethod
    def get_model(
        model_name: str,
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> AbstractConnector:
        provider_model = MODEL_PROVIDER_MAP.get(model_name)
        if provider_model is not None:
            connector_cls = _CONNECTOR_OVERRIDES.get(model_name) or _load_litellm()
        elif model_name.startswith(LITELLM_PREFIX):
            # Escape hatch: ``litellm:<model>`` runs any model string LiteLLM
            # understands (e.g. ``litellm:gemini/gemini-1.5-pro``,
            # ``litellm:ollama/llama3``) without pre-registering a logical
            # name — so the UI isn't limited to MODEL_PROVIDER_MAP. A bare
            # unknown name still raises, to catch typos.
            connector_cls = _load_litellm()
            provider_model = model_name[len(LITELLM_PREFIX) :].strip()
            if not provider_model:
                raise ValueError("Empty LiteLLM model string after 'litellm:' prefix.")
        else:
            raise ValueError(
                f"Unsupported model {model_name!r}. "
                f"Known models: {sorted(MODEL_PROVIDER_MAP)}. "
                f"For any other model, prefix a LiteLLM model string with "
                f"'{LITELLM_PREFIX}' (e.g. '{LITELLM_PREFIX}gemini/gemini-1.5-pro')."
            )

        # Demo mode overrides the connector class with the offline fake, but
        # only when no explicit per-name override is registered (test fakes
        # installed via register_model still win, so the suite is unaffected).
        # The model name is still validated above, so typos fail fast even in
        # demo mode.
        if demo_mode_active() and model_name not in _CONNECTOR_OVERRIDES:
            from src.llm_connectors.demo_connector import DemoConnector

            connector_cls = DemoConnector

        connector = connector_cls(provider_model)

        # Thread generation params onto the connector. The old code passed
        # only ``provider_model``, leaving each connector's max_tokens /
        # temperature unreachable (Anthropic was hard-capped at 1024). We
        # set them as attributes (when the connector exposes them) rather
        # than via the ctor so heterogeneous / test connector signatures
        # don't break. Explicit args win over the FAIRGAME_LLM_* env defaults.
        if max_tokens is None:
            max_tokens = int_env("FAIRGAME_LLM_MAX_TOKENS")
        if temperature is None:
            temperature = float_env("FAIRGAME_LLM_TEMPERATURE")
        if max_tokens is not None and hasattr(connector, "max_tokens"):
            connector.max_tokens = max_tokens
        if temperature is not None and hasattr(connector, "temperature"):
            connector.temperature = temperature
        return connector


def execute_prompt(
    model_name: str,
    prompt: str,
    *,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> str:
    """Execute ``prompt`` using the connector registered for ``model_name``."""
    chat_model = ChatModelFactory.get_model(
        model_name, max_tokens=max_tokens, temperature=temperature
    )
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
