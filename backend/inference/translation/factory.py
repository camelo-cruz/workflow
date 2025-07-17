from inference.translation.abstract import TranslationStrategy
from inference.translation.custom import CustomTranslationStrategy
from inference.translation.deepl import DeeplStrategy
from inference.translation.marian import MarianStrategy
from inference.translation.M2M100 import M2M100Strategy


class TranslationStrategyFactory:
    @staticmethod
    def get_strategy(language_code: str, translationModel: str = None) -> TranslationStrategy:
        if translationModel:
            return CustomTranslationStrategy(language_code, translationModel)
        elif language_code in ['tr', 'de']:
            return DeeplStrategy(language_code)
        elif language_code in ['en']:
            try:
                return MarianStrategy(language_code)
            except Exception as e:
                return M2M100Strategy(language_code)
        else:
            raise ValueError(f"No pretrained translation strategy available for language code: {language_code}")
