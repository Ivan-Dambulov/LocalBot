from abc import ABC, abstractmethod

class BaseLLM(ABC):
    @abstractmethod
    def generate(self, messages):
        raise NotImplementedError

    @abstractmethod
    def stream(self, messages):
        raise NotImplementedError