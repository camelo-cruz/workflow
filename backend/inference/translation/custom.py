from inference.translation.abstract import TranslationStrategy

class CustomTranslationStrategy(TranslationStrategy):
    def __init__(self, language_code: str, device: str = "cpu"):
        super().__init__(language_code, device)
    
    def load_model(self, model_name):
        self._init_M2M100_model(model_path=f"models/translation/{model_name}")

    def translate(self, text: str) -> str | None:
        #out = self._translate_marian(text)
        out = self._translate_M2M100(text)
        return out