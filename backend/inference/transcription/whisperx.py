import whisperx
from whisperx.diarize import DiarizationPipeline


from inference.transcription.abstract import TranscriptionStrategy


class WhisperxStrategy(TranscriptionStrategy):
    def __init__(self, *args, **kwargs):
        """
        Initialize the Whisperx transcription strategy.	"""
        super().__init__(*args, **kwargs)
        self.batch_size = kwargs.get('batch_size', 8)
    
    def load_model(self):
        try:
            self.model = whisperx.load_model("large-v2", self.device, compute_type="float16", language=self.language_code)
        except:
            self.model = whisperx.load_model("large-v2", self.device, compute_type="int8", language=self.language_code)
        finally:
            print(f"Whisperx model loaded on device {self.device}")

    def transcribe(self, path_to_audio):
        audio = whisperx.load_audio(path_to_audio)
        result = self.model.transcribe(audio, batch_size=self.batch_size, language=self.language_code)

        model_a, metadata = whisperx.load_align_model(
            language_code=result["language"],
            device=self.device)
        result = whisperx.align(result["segments"], model_a, metadata, audio, self.device)

        diarize_model = DiarizationPipeline(
            use_auth_token=self.hugging_key,
            device=self.device
        )
        diarize_segments = diarize_model(audio)
        result = whisperx.assign_word_speakers(diarize_segments, result)


        full_sentences, buffer_speaker, buffer_text = [], None, ""
        for seg in result["segments"]:
            spk = seg.get("speaker", buffer_speaker)
            if spk is None:
                continue
            txt = seg["text"].strip()

            if buffer_speaker is None:
                buffer_speaker, buffer_text = spk, txt
            elif spk == buffer_speaker:
                buffer_text += " " + txt
            else:
                full_sentences.append(f"{buffer_speaker}: {buffer_text}")
                buffer_speaker, buffer_text = spk, txt

        if buffer_speaker:
            full_sentences.append(f"{buffer_speaker}: {buffer_text}")

        joined_text = "  ".join(full_sentences)

        print('joined_text: ', joined_text)
        
        return joined_text
    
