"""Unified LLM connector backed by LiteLLM.

Every provider (OpenAI, Anthropic, Mistral, DeepSeek, local Ollama, …) is
reached through a single ``litellm.completion`` call, so FAIRGAME no longer
ships per-provider SDK code. LiteLLM reads API keys from the provider-standard
environment variables (``OPENAI_API_KEY``, ``ANTHROPIC_API_KEY``,
``MISTRAL_API_KEY``, ``DEEPSEEK_API_KEY``, …); locally-served models (e.g.
``ollama/…``) need no key.

The retry / rate-limit / throttle / logging machinery lives in
:class:`AbstractConnector`; this class only implements ``_send_prompt``.
"""

from __future__ import annotations

from litellm import completion
from litellm.exceptions import (
    APIConnectionError,
    InternalServerError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
)

from src.llm_connectors.abstract_connector import AbstractConnector


class LiteLLMConnector(AbstractConnector):
    """Send prompts to any LiteLLM-supported model.

    ``provider_model`` is a LiteLLM model string (e.g. ``"gpt-4o"``,
    ``"anthropic/claude-sonnet-4-6"``, ``"mistral/mistral-large-latest"``,
    ``"ollama/llama3"``).
    """

    # LiteLLM normalises every provider's transient failures onto these
    # OpenAI-style exception types; treat them as retryable.
    RETRYABLE_EXCEPTIONS = AbstractConnector.RETRYABLE_EXCEPTIONS + (
        RateLimitError,
        APIConnectionError,
        ServiceUnavailableError,
        InternalServerError,
        Timeout,
    )

    def __init__(self, provider_model: str) -> None:
        super().__init__()
        self.provider_model = provider_model
        # Set by the factory from explicit args / FAIRGAME_LLM_* env defaults.
        self.max_tokens = None
        self.temperature = None

    def _send_prompt(self, prompt: str) -> str:
        kwargs = {
            "model": self.provider_model,
            "messages": [{"role": "user", "content": prompt}],
            "timeout": self.REQUEST_TIMEOUT_SECONDS,
        }
        if self.max_tokens is not None:
            kwargs["max_tokens"] = self.max_tokens
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature
        response = completion(**kwargs)
        content = response.choices[0].message.content
        if not content:
            raise ValueError(f"{self.provider_model} returned empty content.")
        return content.strip()
