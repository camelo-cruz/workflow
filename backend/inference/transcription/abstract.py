import os
from abc import ABC, abstractmethod
from pathlib import Path
from dotenv import load_dotenv

_this_file = Path(__file__).resolve()
parent_dir = _this_file.parent.parent.parent

class TranscriptionStrategy(ABC):
    def __init__(self, language_code: str, device: str = "cpu"):
        self.language_code = language_code.lower()
        self.device = device
        self.hugging_key = self._load_hugging_face_token()
        self.load_model()
    
    def _load_hugging_face_token(self):
        token = os.getenv("HUGGING_KEY", "").strip()
        if not token:
            secrets_path = os.path.join(parent_dir, 'materials', 'secrets.env')
            print(f"Loading Hugging Face token from {secrets_path}")
            if os.path.exists(secrets_path):
                load_dotenv(secrets_path, override=True)
                token = os.getenv("HUGGING_KEY", "").strip()
        if not token:
            raise ValueError("Hugging Face key not found. Set it in HUGGING_KEY")
        return token
    
    @abstractmethod
    def load_model(self):
        """
        Load the transcription models needed for the strategy.

        Subclasses must implement this method. Typical responsibilities may include
        loading specific ASR (automatic speech recognition) models.

        This ensures each subclass is responsible for preparing its required resources.
        """
        raise NotImplementedError(
            "Subclasses must implement load_model() to initialize their transcription models. "
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
