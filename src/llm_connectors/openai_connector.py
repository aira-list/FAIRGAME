"""OpenAI chat-completion connector."""

from __future__ import annotations

import os

from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError

from src.llm_connectors.abstract_connector import AbstractConnector


class OpenAIConnector(AbstractConnector):
    """Concrete connector for OpenAI's chat completion API."""

    RETRYABLE_EXCEPTIONS = (APIConnectionError, APITimeoutError, RateLimitError)

    def __init__(self, provider_model: str, temperature: float = 1.0) -> None:
        super().__init__()
        api_key = os.getenv("API_KEY_OPENAI")
        if not api_key:
            raise EnvironmentError("API_KEY_OPENAI not found in environment variables.")
        self.provider_model = provider_model
        self.temperature = temperature
        self.client = OpenAI(api_key=api_key, timeout=60.0)

    def _send_prompt(self, prompt: str) -> str:
        completion = self.client.chat.completions.create(
            model=self.provider_model,
            temperature=self.temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        return completion.choices[0].message.content
