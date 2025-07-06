import os
import whisper
from inference.transcription.abstract import TranscriptionStrategy

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)


class WhisperStrategy(TranscriptionStrategy):
    def __init__(self, *args, **kwargs):
        """
        Initializes the Whisper transcription strategy.

        Args:
            *args: Positional arguments.
            **kwargs: Keyword arguments, including 'input_dir', 'language', and 'device'.
        """
        super().__init__(*args, **kwargs)
    
    def load_model(self):
         self.model = whisper.load_model("large-v2", self.device)

    def transcribe(self, path_to_audio):
        res = self.model.transcribe(path_to_audio, language=self.language_code)
        return res["text"]