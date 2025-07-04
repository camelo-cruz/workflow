from inference.translation.abstract import TranslationStrategy
from inference.translation.custom import CustomTranslationStrategy
from inference.translation.deepl import DeeplStrategy
from inference.translation.marian import MarianStrategy
from inference.translation.M2M100 import M2M100Strategy


class TranslationStrategyFactory:
    @staticmethod
    def get_strategy(language_code: str, custom_translation_model: str = None) -> TranslationStrategy:
        if custom_translation_model:
            return CustomTranslationStrategy(language_code, custom_translation_model)
        elif language_code in ["yo", 'de']:
            return M2M100Strategy(language_code)
        else:
            raise ValueError(f"No pretrained translation strategy available for language code: {language_code}")
