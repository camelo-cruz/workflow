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

        strategy_chain = []
        if language_code in ['tr', 'de', 'pt']:
            strategy_chain = [DeeplStrategy, MarianStrategy, M2M100Strategy]
        elif language_code == 'yo':
            strategy_chain = [MarianStrategy, M2M100Strategy]
        else:
            raise ValueError(f"No pretrained translation strategy available for language code: {language_code}")

        for Strategy in strategy_chain:
            try:
                return Strategy(language_code)
            except Exception as e:
                print(f"{Strategy.__name__} failed for {language_code}: {e}")

        raise RuntimeError(f"All translation strategies failed for {language_code}")