import abc

class AbstractConnector(abc.ABC):
    """
    Abstract base class for chat models.
    """

    @abc.abstractmethod
    def send_prompt(self, prompt: str) -> str:
        """
        Send a prompt to the chat API and return the response text.

        Parameters:
            prompt (str): The user prompt.

        Returns:
            str: The API's response.
        """
        pass
