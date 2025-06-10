from inference.translation.abstract import TranslationStrategy

class DefaultTranslationStrategy(TranslationStrategy):
    """
    A default chain: Marian → DeepL.
    We explicitly call `load_model()` in __init__ so that both backends
    are loaded at construction time.
    """
    def __init__(self, language_code: str, device: str = "cpu"):
        super().__init__(language_code, device)
    
    def load_model(self):
        self._init_deepl_client()
        self._init_marian_model()

    def translate(self, text: str) -> str | None:
        try:
            return self._translate_deepl(text)
        except Exception as e1:
            print(f"[Fallback] DeepL failed: {e1}")
            try:
                return self._translate_marian(text)
            except Exception as e2:
                print(f"[Error] Marian also failed: {e2}")
                return None
