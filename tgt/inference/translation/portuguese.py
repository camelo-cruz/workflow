# translation/portuguese.py

from transformers import MarianMTModel, MarianTokenizer
from inference.translation.abstract import TranslationStrategy
import os
import sys
import deepl
from dotenv import load_dotenv

class PortugueseTranslationStrategy(TranslationStrategy):
    def __init__(self, device: str = "cpu"):
        super().__init__("pt", device)

    def load_model(self):
        # Load your custom local model (converted from OPUS)
        local_model_path = os.path.join(os.path.dirname(__file__), "converted/opus-mt-pt-en")
        try:
            self._marian_tokenizer = MarianTokenizer.from_pretrained(local_model_path)
            self._marian_model = MarianMTModel.from_pretrained(local_model_path).to(self.device)
        except Exception as e:
            print(f"[PortugueseTranslationStrategy] Warning: Marian model could not be loaded: {e}")

 
    def translate(self, text: str) -> str | None:
        try:
            inputs = self._marian_tokenizer([text], return_tensors="pt", padding=True, truncation=True).to(self.device)
            outputs = self._marian_model.generate(**inputs)
            return self._marian_tokenizer.batch_decode(outputs, skip_special_tokens=True)[0]
        except Exception as e:
            print(f"[PortugueseTranslationStrategy] Marian translation failed: {e}")

