from inference.translation.abstract import TranslationStrategy
from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer

class M2M100Strategy(TranslationStrategy):
    def __init__(self, language_code, device: str = "cpu"):
        super().__init__(language_code, device)

    def load_model(self, model_path = None):
        if model_path:
            self._M2_M100_model = M2M100ForConditionalGeneration.from_pretrained(model_path)
            self._M2_M100_tokenizer = M2M100Tokenizer.from_pretrained(model_path)
        else:
            self._M2_M100_model = M2M100ForConditionalGeneration.from_pretrained("facebook/m2m100_1.2B")
            self._M2_M100_tokenizer = M2M100Tokenizer.from_pretrained("facebook/m2m100_1.2B")

    def translate(self, text: str) -> str | None:
        self._M2_M100_tokenizer.src_lang = self.language_code
        encoded_hi = self._M2_M100_tokenizer(text, return_tensors="pt")
        generated_tokens = self._M2_M100_model.generate(**encoded_hi, forced_bos_token_id=self._M2_M100_tokenizer.get_lang_id("en"))
        decoded = self._M2_M100_tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)

        return decoded
