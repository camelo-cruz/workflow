import torch
from transformers import pipeline
from inference.transcription.abstract import TranscriptionStrategy


class BengaliStrategy(TranscriptionStrategy):
    def load_model(self):
        self.device = 0 if (torch.cuda.is_available()) else "cpu"
        self.whisper_asr = pipeline(
            "automatic-speech-recognition",
            model="mozilla-ai/whisper-large-v3-bn",
            device=self.device
        )

    def transcribe(self, path_to_audio: str):
        self.whisper_asr.model.config.forced_decoder_ids = (
            self.whisper_asr.tokenizer.get_decoder_prompt_ids(language=self.language_code, task="transcribe")
        )

        result = self.whisper_asr(path_to_audio)
        result = result.get("text", "").strip()
        print(result)
        return result