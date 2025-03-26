
from mistralai import Mistral
import os 

from src.llm_connectors.abstract_connector import AbstractConnector

class MistralConnector(AbstractConnector):
    """
    Chat model implementation for the Mistral API.
    """

    def __init__(self, provider_model: str):
        self.api_key = os.getenv("API_KEY_MISTRAL")
        if not self.api_key:
            raise EnvironmentError("API_KEY_MISTRAL not found in environment variables.")
        self.provider_model = provider_model
        self.client = Mistral(api_key=self.api_key)

    def send_prompt(self, prompt: str) -> str:
        response = self.client.chat.complete(
            model=self.provider_model,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
