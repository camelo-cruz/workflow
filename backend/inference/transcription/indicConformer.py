import torch
import nemo.collections.asr as nemo_asr

from inference.transcription.abstract import TranscriptionStrategy
from whisper_jax import FlaxWhisperForConditionalGeneration, FlaxWhisperPipline
import jax.numpy as jnp


class IndicConformerStrategy(TranscriptionStrategy):
    def load_model(self):
        self.model = nemo_asr.models.ASRModel.from_pretrained("ai4bharat/indicconformer_stt_bn_hybrid_rnnt_large")

    def transcribe(self, path_to_audio: str) -> str:
        """
        Convert input audio to mono 16 kHz WAV and run inference.
        Returns the decoded transcript.
        """
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.freeze() # inference mode
        self.model = self.model.to(device) # transfer model to device
