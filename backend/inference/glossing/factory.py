from inference.glossing.abstract import GlossingStrategy
from inference.glossing.default import DefaultGlossingStrategy
from inference.glossing.japanese import JapaneseGlossingStrategy
from inference.glossing.vietnamese import VietnameseGlossingStrategy
from inference.glossing.portuguese import PortugueseGlossingStrategy


class GlossingStrategyFactory:
    @staticmethod
    def get_strategy(language_code: str) -> GlossingStrategy:
        if language_code in ["de", "uk", "ru", "en", "it"]:
            return DefaultGlossingStrategy(language_code)
        if language_code == "ja":
            return JapaneseGlossingStrategy(language_code)
        elif language_code == "vi":
            return VietnameseGlossingStrategy(language_code)
        elif language_code == "pt":
            return PortugueseGlossingStrategy(language_code)
        else:
            raise ValueError(f"No glossing strategy available for language code: {language_code}")