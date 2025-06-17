from inference.transliteration.abstract import TransliterationStrategy
from inference.transliteration.japanese import JapaneseStrategy
from inference.transliteration.chinese import ChineseStrategy

class TransliterationStrategyFactory:
    @staticmethod
    def get_strategy(language_code: str) -> TransliterationStrategy:
        if language_code == "zh":
            return ChineseStrategy()
        else:
            raise ValueError(f"No transliteration strategy available for language code: {language_code}")
            
