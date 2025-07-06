from abc import ABC, abstractmethod

class TranscriptionStrategy(ABC):
    def __init__(self, language_code: str, device: str = "cpu"):
        self.language_code = language_code.lower()
        self.device = device
    
    @abstractmethod
    def load_model(self):
        """
        Load the Transcription models. This method can be called by subclasses
        to ensure that both Marian and DeepL are initialized.
        """
        raise NotImplementedError(
            "Subclasses must implement load_model() to initialize their translation models. you can call "
            "self._init_marian_model() and/or self._init_deepl_client() as needed."
        )
        
    @abstractmethod
    def transcribe(self, text: str) -> str | None:
        """
        Transcribe the given text using the strategy's model.
        """
        raise NotImplementedError("Subclasses must implement transcribe()")
