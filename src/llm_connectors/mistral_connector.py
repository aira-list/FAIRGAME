"""Mistral AI chat connector."""

from __future__ import annotations

import os

from mistralai import Mistral

from src.llm_connectors.abstract_connector import AbstractConnector


class MistralConnector(AbstractConnector):
    """Concrete connector for Mistral's chat completion API."""

    # Mistral SDK does not currently expose typed retryable errors, so we
    # rely on the default (Exception) tuple from the base class.

    def __init__(self, provider_model: str) -> None:
        super().__init__()
        api_key = os.getenv("API_KEY_MISTRAL")
        if not api_key:
            raise EnvironmentError(
                "API_KEY_MISTRAL not found in environment variables."
            )
        self.provider_model = provider_model
        self.client = Mistral(api_key=api_key)

    def _send_prompt(self, prompt: str) -> str:
        response = self.client.chat.complete(
            model=self.provider_model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content
