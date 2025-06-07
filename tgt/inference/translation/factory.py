from .abstract import TranslationStrategy
from .default import DefaultTranslationStrategy


class TranslationStrategyFactory:
    @staticmethod
    def get_strategy(language_code: str) -> TranslationStrategy:
        return DefaultTranslationStrategy(language_code)
