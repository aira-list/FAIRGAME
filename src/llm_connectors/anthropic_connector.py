"""Anthropic Claude chat connector."""

from __future__ import annotations

import os

from anthropic import (
    Anthropic,
    APIConnectionError,
    APITimeoutError,
    RateLimitError,
)

from src.llm_connectors.abstract_connector import AbstractConnector


class AnthropicConnector(AbstractConnector):
    """Concrete connector for Anthropic's Claude messages API."""

    RETRYABLE_EXCEPTIONS = (APIConnectionError, APITimeoutError, RateLimitError)

    def __init__(self, provider_model: str, max_tokens: int = 1024) -> None:
        super().__init__()
        api_key = os.getenv("API_KEY_ANTHROPIC")
        if not api_key:
            raise EnvironmentError(
                "API_KEY_ANTHROPIC not found in environment variables."
            )
        self.provider_model = provider_model
        self.max_tokens = max_tokens
        self.client = Anthropic(api_key=api_key, timeout=60.0)

    def _send_prompt(self, prompt: str) -> str:
        response = self.client.messages.create(
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}],
            model=self.provider_model,
        )
        return response.content[0].text
