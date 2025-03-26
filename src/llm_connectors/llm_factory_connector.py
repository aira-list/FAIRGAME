
from dotenv import load_dotenv
from src.llm_connectors.anthropic_connector import AnthropicConnector
from src.llm_connectors.mistral_connector import MistralConnector
from src.llm_connectors.openai_connector import OpenAIConnector

# Load environment variables from a .env file
load_dotenv()

# Dictionary mapping our abstract model names to provider classes and their corresponding provider model identifiers.
MODEL_PROVIDER_MAP = {
    "Claude35Sonnet": (AnthropicConnector, "claude-3-5-sonnet-20241022"),
    "MistralLarge": (MistralConnector, "mistral-large-latest"),
    "OpenAIGPT4o": (OpenAIConnector, "gpt-4o"),
    # Add more mappings as needed.
}

class ChatModelFactory:
    """
    Factory for creating chat model instances based on the model name.
    """

    @staticmethod
    def get_model(model_name: str):
        """
        Return an instance of ChatModel based on the provided model name.

        Parameters:
            model_name (str): The abstract model name (e.g., "MistralLarge", "GPT4", "Claude").

        Returns:
            ChatModel: An instance of the appropriate chat model.

        Raises:
            ValueError: If the model_name is unsupported.
        """
        provider_info = MODEL_PROVIDER_MAP.get(model_name)
        if not provider_info:
            raise ValueError(f"Unsupported model specified: {model_name}")
        model_class, provider_model = provider_info
        return model_class(provider_model)


def execute_prompt(model_name: str, prompt: str) -> str:
    """
    Execute a prompt using the specified model.

    Parameters:
        model_name (str): The abstract model name (e.g., "MistralLarge", "GPT4", "Claude").
        prompt (str): The prompt text to send to the API.

    Returns:
        str: The response text from the API.
    """
    chat_model = ChatModelFactory.get_model(model_name)
    return chat_model.send_prompt(prompt)


if __name__ == "__main__":
    # Example usage:
    model_identifier = "Claude35Sonnet"
    prompt_text = "Tell me a programming joke."
    
    try:
        result = execute_prompt(model_identifier, prompt_text)
        print("API Response:", result)
    except Exception as e:
        print("An error occurred:", e)
