from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)

path = os.path.join(parent_dir, "whisper_models", "whisperx")

model = AutoModelForSpeechSeq2Seq.from_pretrained(path, device_map="auto")
processor = AutoProcessor.from_pretrained(path)
