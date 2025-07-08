from inference.translation.abstract import TranslationStrategy

class CustomTranslationStrategy(TranslationStrategy):
    
    def load_model(self):
        #self._init_M2M100_model(model_path=f"models/translation/{model_name}")
        self._init_M2M100_model(model_path=f"models/translation/{self.translationModel}")

    def translate(self, text: str) -> str | None:
        #out = self._translate_marian(text)
        out = self._translate_M2M100(text)
        return out