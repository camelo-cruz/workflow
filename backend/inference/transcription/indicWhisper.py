from inference.transcription.abstract import TranscriptionStrategy
from whisper_jax import FlaxWhisperForConditionalGeneration, FlaxWhisperPipline
import jax.numpy as jnp


class IndicWhisperStrategy(TranscriptionStrategy):
    def load_model(self):
        self.model = FlaxWhisperPipline('parthiv11/indic_whisper_nodcil', dtype=jnp.bfloat16)

    def transcribe(self, path_to_audio: str) -> str:
        """
        Convert input audio to mono 16 kHz WAV and run inference.
        Returns the decoded transcript.
        """
        transcript= self.model(path_to_audio, language=self.language_code)
        text = transcript['text']
        print(text)
        return text