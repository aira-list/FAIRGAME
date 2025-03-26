from openai import OpenAI
import os 

from src.llm_connectors.abstract_connector import AbstractConnector

class OpenAIConnector(AbstractConnector):
    """
    Chat model implementation for the OpenAI API.
    """

    def __init__(self, provider_model: str, temperature: float = 1.0):
        self.api_key = os.getenv("API_KEY_OPENAI")
        if not self.api_key:
            raise EnvironmentError("API_KEY_OPENAI not found in environment variables.")
        self.provider_model = provider_model
        self.temperature = temperature
        self.client = OpenAI(api_key=self.api_key)

    def send_prompt(self, prompt: str) -> str:
        messages = [{"role": "user", "content": prompt}]
        completion = self.client.chat.completions.create(
            model=self.provider_model,
            temperature=self.temperature,
            messages=messages
        )
        return completion.choices[0].message.content
