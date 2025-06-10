from inference.translation.abstract import TranslationStrategy
from inference.translation.default import DefaultTranslationStrategy


class TranslationStrategyFactory:
    @staticmethod
    def get_strategy(language_code: str) -> TranslationStrategy:
        if language_code in ["de", "uk", "ru", "en", "it"]:
            return DefaultTranslationStrategy(language_code)
        else:
            raise ValueError(f"No translation strategy available for language code: {language_code}")
