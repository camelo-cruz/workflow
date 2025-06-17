from inference.transliteration.abstract import TransliterationStrategy
from transliterate import translit

class RussianStrategy(TransliterationStrategy):
    def transliterate(self, sentence: str) -> str:
        return translit(sentence, 'ru', reversed=True)