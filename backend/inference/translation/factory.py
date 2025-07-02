from inference.translation.abstract import TranslationStrategy
from inference.translation.default import DefaultTranslationStrategy
from inference.translation.custom import CustomTranslationStrategy


class TranslationStrategyFactory:
    @staticmethod
    def get_strategy(language_code: str, custom_translation_model: str = None) -> TranslationStrategy:
        if custom_translation_model:
            return CustomTranslationStrategy(language_code, custom_translation_model)
        else:
            if language_code in ["de", "uk", "ru", "en", "it"]:
                return DefaultTranslationStrategy(language_code)
            else:
                raise ValueError(f"No pretrained translation strategy available for language code: {language_code}")
