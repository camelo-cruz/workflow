from inference.translation.abstract import TranslationStrategy

class DefaultTranslationStrategy(TranslationStrategy):
    """A default chain: Marian → DeepL."""

    def __init__(self, language_code: str, device: str = "cpu"):
        super().__init__(language_code, device)
        self.load_model()  # Call load_model here

    def load_model(self):
        self._init_deepl_client()
        self._init_marian_model()

    def translate(self, text: str) -> str | None:
        try:
            out = self._translate_deepl(text)
            return out
        except Exception as e1:
            print(f"DeepL translation failed: {e1}")
            try:
                out = self._translate_marian(text)
                return out
            except Exception as e2:
                print(f"Marian translation failed: {e2}")
                return None
