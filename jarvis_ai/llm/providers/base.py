from abc import ABC, abstractmethod

class LLMProviderBase(ABC):
    @abstractmethod
    def generate(self, prompt, system_prompt=None, temperature=0.7, max_tokens=500):
        """
        Generate a response from the LLM provider.
        """
        pass
