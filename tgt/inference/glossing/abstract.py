from abc import ABC, abstractmethod

class GlossingStrategy(ABC):
    """
    Abstract base class for glossing strategies.
    Subclasses must implement:
      - load_model()
      - gloss_sentence(sentence: str) -> str
    """
    def __init__(self, language_code: str):
        self.language_code = language_code

    @abstractmethod
    def load_model(self):
        raise NotImplementedError("Subclasses must implement load_model()")

    @abstractmethod
    def gloss(self, sentence: str) -> str:
        raise NotImplementedError("Subclasses must implement gloss_sentence()")
