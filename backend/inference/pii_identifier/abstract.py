from abc import ABC, abstractmethod

class PIIStrategy(ABC):
    def __init__(self, language_code: str):
        self.lang = language_code.lower()
        self.nlp = None
        self.load_model()
    
    @abstractmethod
    def load_model(self):
        """
        Subclasses must implement this to load their specific NER model.
        """
        raise NotImplementedError("Subclasses must implement load_model()")
        
    @abstractmethod
    def identify_and_annotate(self, text: str) -> str | None:
        """
        Subclasses must implement this.
        """
        raise NotImplementedError("Subclasses must implement translate()")
