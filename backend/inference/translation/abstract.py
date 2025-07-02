# strategies.py

import os
import sys
from abc import ABC, abstractmethod

import deepl
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer


class TranslationStrategy(ABC):
    def __init__(self, language_code: str, device: str = "cpu"):
        self.language_code = language_code.lower()
        self.device = device

        self._marian_model = None
        self._marian_tokenizer = None
        self._deepl_client = None
        self._deepl_source_lang = None


    def _init_marian_model(self):
        """
        Attempt to load a MarianMT model for <language_code>→en.
        If it fails, _marian_model and _marian_tokenizer stay as None.
        """
        if self.language_code == "yo":
            model_name = f"Helsinki-NLP/opus-mt-mul-en"
        else:
            model_name = f"Helsinki-NLP/opus-mt-{self.language_code}-en"
        self._marian_tokenizer = AutoTokenizer.from_pretrained(model_name)
        self._marian_model = (
            AutoModelForSeq2SeqLM.from_pretrained(model_name)
            .to(self.device)
        )
    
    def _init_M2M100_model(self, model_path = None):
        if model_path:
            self._M2_M100_model = M2M100ForConditionalGeneration.from_pretrained(model_path)
            self._M2_M100_tokenizer = M2M100Tokenizer.from_pretrained(model_path)
        else:
            self._M2_M100_model = M2M100ForConditionalGeneration.from_pretrained("facebook/m2m100_1.2B")
            self._M2_M100_tokenizer = M2M100Tokenizer.from_pretrained("facebook/m2m100_1.2B")

    def _init_deepl_client(self):
        """
        Attempt to create a DeepL client. If the API key is missing
        or DeepL is unreachable, leave them as None.
        """
        base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        secrets_path = os.path.join(base_path, "materials", "secrets.env")
        from dotenv import load_dotenv
        load_dotenv(secrets_path, override=True)
        api_key = os.getenv("DEEPL_API_KEY")
        if not api_key:
            raise RuntimeError("DeepL API_KEY missing or invalid")

        self._deepl_client = deepl.DeepLClient(api_key)
        # Normalize “PT → PT-BR” for DeepL
        code = self.language_code.upper()
        if code.lower() == "pt":
            code = "PT-BR"
        self._deepl_source_lang = code

    def _translate_marian(self, text: str) -> str | None:
        """
        If the Marian model was successfully loaded, run a forward pass.
        Otherwise return None.
        """
        if not self._marian_model or not self._marian_tokenizer:
            raise RuntimeError(
                "Marian model or tokenizer not initialized. "
                "Call _init_marian_model() before translating."
            )

        try:
            inputs = self._marian_tokenizer.encode(text, return_tensors="pt")
            outputs = self._marian_model.generate(inputs, num_beams=4, max_length=50, early_stopping=True)
            translated_text = self._marian_tokenizer.decode(outputs[0], skip_special_tokens=True)

            return translated_text

        except Exception:
            return None

    def _translate_deepl(self, text: str) -> str | None:
        """
        If the DeepL client was successfully created, call it.
        Otherwise return None.
        """
        if not self._deepl_client:
            raise RuntimeError(
                "DeepL client not initialized. "
                "Call _init_deepl_client() before translating."
            )

        try:
            # First try explicit source_lang; if that fails, let DeepL auto-detect
            try:
                result = self._deepl_client.translate_text(
                    text,
                    source_lang=self._deepl_source_lang,
                    target_lang="EN-US"
                )
            except deepl.DeepLException:
                result = self._deepl_client.translate_text(text, target_lang="EN-US")

            return result.text
        except Exception:
            return None
    
    def _translate_M2M100(self, text: str) -> str | None:
        self._M2_M100_tokenizer.src_lang = self.language_code
        encoded_hi = self._M2_M100_tokenizer(text, return_tensors="pt")
        generated_tokens = self._M2_M100_model.generate(**encoded_hi, forced_bos_token_id=self._M2_M100_tokenizer.get_lang_id("en"))
        decoded = self._M2_M100_tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)

        return decoded
    
    @abstractmethod
    def load_model(self):
        """
        Load the translation models. This method can be called by subclasses
        to ensure that both Marian and DeepL are initialized.
        """
        raise NotImplementedError(
            "Subclasses must implement load_model() to initialize their translation models. you can call "
            "self._init_marian_model() and/or self._init_deepl_client() as needed."
        )
        
    @abstractmethod
    def translate(self, text: str) -> str | None:
        """
        Subclasses must implement this. They can call:
            - self._translate_marian(text)
            - self._translate_deepl(text)
            - or any other provider-specific helper they load themselves

        Return a non-None string on success, or None on failure.
        """
        raise NotImplementedError("Subclasses must implement translate()")
