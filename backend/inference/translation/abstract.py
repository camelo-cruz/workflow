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
        Load the translation models. This method can be called by subclasses
        to ensure that both Marian and DeepL are initialized.
        """
        raise NotImplementedError(
            "Subclasses must implement load_model() to initialize their translation models. you can call "
            "self._init_marian_model() and/or self._init_deepl_client() as needed."
        )
        
    @abstractmethod
    def translate(self, text: str) -> str | None:
        """
        Subclasses must implement this. They can call:
            - self._translate_marian(text)
            - self._translate_deepl(text)
            - or any other provider-specific helper they load themselves

        Return a non-None string on success, or None on failure.
        """
        raise NotImplementedError("Subclasses must implement translate()")
