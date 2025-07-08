from abc import ABC, abstractmethod

# Define an abstract base class for different transcription strategies.
# It enforces a consistent interface across all transcription implementations.
class TranscriptionStrategy(ABC):
    def __init__(self, language_code: str, device: str = "cpu"):
        self.language_code = language_code.lower()
        self.device = device
        self.load_model()
    
    @abstractmethod
    def load_model(self):
        """
        Load the transcription models needed for the strategy.

        Subclasses must implement this method. Typical responsibilities may include
        loading specific ASR (automatic speech recognition) models or initializing
        external clients (e.g., DeepL, Marian).

        This ensures each subclass is responsible for preparing its required resources.
        """
        raise NotImplementedError(
            "Subclasses must implement load_model() to initialize their transcription models. "
            "You can call self._init_marian_model() and/or self._init_deepl_client() as needed."
        )
        
    @abstractmethod
    def transcribe(self, text: str) -> str | None:
        """
        Transcribe the given text using the model implemented by the subclass.

        Arguments:
            text (str): The input string to transcribe, which could be a result of speech recognition
                        or another input source depending on the use case.

        Returns:
            str | None: The transcribed (processed) version of the input text,
                        or None if transcription cannot be performed.

        This method must be implemented by subclasses to define their core logic.
        """
        raise NotImplementedError("Subclasses must implement transcribe()")
