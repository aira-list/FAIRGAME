from anthropic import Anthropic
import os

from src.llm_connectors.abstract_connector import AbstractConnector

class AnthropicConnector(AbstractConnector):
    """
    Chat model implementation for the Claude API (Anthropic).
    """

    def __init__(self, provider_model: str, max_tokens: int = 1024):
        self.api_key = os.getenv("API_KEY_ANTHROPIC")
        if not self.api_key:
            raise EnvironmentError("API_KEY_ANTHROPIC not found in environment variables.")
        self.provider_model = provider_model
        self.max_tokens = max_tokens
        self.client = Anthropic(api_key=self.api_key)

    def send_prompt(self, prompt: str) -> str:
        response = self.client.messages.create(
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}],
            model=self.provider_model,
        )
        return response.content[0].text