from inference.translation.abstract import TranslationStrategy

class CustomTranslationStrategy(TranslationStrategy):
    def __init__(self, language_code: str, custom_translation_model = None, device: str = "cpu"):
        super().__init__(language_code, device)
        self.custom_translation_model = custom_translation_model
    
    def load_model(self):
        #self._init_M2M100_model(model_path=f"models/translation/{model_name}")
        self._init_M2M100_model(model_path=f"models/translation/{self.custom_translation_model}")

    def translate(self, text: str) -> str | None:
        #out = self._translate_marian(text)
        out = self._translate_M2M100(text)
        return out
    
if __name__ == "__main__":
    translation_strategy = CustomTranslationStrategy(language_code="yo", 
                                               custom_translation_model="yo_H_custom_translation")
    translation_strategy.load_model()
    sentence = "ajá méjì tí àgùntàn kan ń mú (ni ó pa àwọ̀ dà)"
    glossed_sentence = translation_strategy.translate(sentence)
    print(glossed_sentence)
