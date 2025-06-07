from .abstract import GlossingStrategy
from .default import DefaultGlossingStrategy
from .japanese import JapaneseGlossingStrategy
from .vietnamese import VietnameseGlossingStrategy
from .portuguese import PortugueseGlossingStrategy


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
            return DefaultGlossingStrategy(language_code)