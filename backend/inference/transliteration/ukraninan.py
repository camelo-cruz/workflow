class UkrainianStrategy(TransliterationStrategy):
    def transliterate(self, sentence: str) -> str:
        return translit(sentence, 'uk', reversed=True)