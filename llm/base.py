from abc import ABC, abstractmethod


class BaseLLM(ABC):

    @abstractmethod
    def generate(self, messages):
        """
        Generate a complete response.
        """
        raise NotImplementedError

    @abstractmethod
    def stream(self, messages):
        """
        Generate a response token-by-token.
        """
        raise NotImplementedError