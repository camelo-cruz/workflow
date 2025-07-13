from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from inference.translation.abstract import TranslationStrategy

class MarianStrategy(TranslationStrategy):

    def load_model(self):
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

    def translate(self, text: str) -> str | None:
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
                outputs = self._marian_model.generate(inputs)
                translated_text = self._marian_tokenizer.decode(outputs[0], skip_special_tokens=True)

                return translated_text

            except Exception:
                return None