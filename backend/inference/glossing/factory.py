from inference.glossing.abstract import GlossingStrategy
from inference.glossing.spacy import SpaCyGlossingStrategy
from inference.glossing.portuguese import PortugueseGlossingStrategy
from inference.glossing.stanza import StanzaGlossingStrategy
from inference.glossing.japanese import JapaneseGlossingStrategy


class GlossingStrategyFactory:
    @staticmethod
    def get_strategy(language_code: str, glossingModel = None, translationModel = None) -> GlossingStrategy:
        if glossingModel:
            return SpaCyGlossingStrategy(language_code, 
                                         glossingModel=glossingModel, 
                                         translationModel=translationModel)
        elif language_code in ['de', 'fi', 'fr', 'el', 'it', 'ro', 'ru', 'uk']:
            return SpaCyGlossingStrategy(language_code)
        elif language_code in ["tr", "vi", "uk", "ru", "en", "it"]:
            return StanzaGlossingStrategy(language_code)
        elif language_code == "pt":
            return PortugueseGlossingStrategy(language_code)
        elif language_code == "ja":
            return JapaneseGlossingStrategy(language_code)
        else:
            raise ValueError(f"No glossing strategy available for language code: {language_code}")