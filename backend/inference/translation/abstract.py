from abc import ABC, abstractmethod

class TranslationStrategy(ABC):
    def __init__(self, language_code: str, translationModel: str = None, device: str = "cpu"):
        self.language_code = language_code.lower()
        self.translationModel = translationModel
        self.device = device
        self.load_model()
    
    @abstractmethod
    def load_model(self):
        """
        Load the translation models. 
        """
        raise NotImplementedError(
            "Subclasses must implement load_model() to initialize their translation models."
        )
        
    @abstractmethod
    def translate(self, text: str) -> str | None:
        """
        Return a non-None string on success, or None on failure.
        """
        raise NotImplementedError("Subclasses must implement translate()")
