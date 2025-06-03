from .gloss_strategy import GlossStrategy
from .default_gloss_strategy import DefaultGlossStrategy
from .japanese_gloss_strategy import JapaneseGlossStrategy
from .vietnamese_gloss_strategy import VietnameseGlossStrategy
from .portuguese_gloss_strategy import PortugueseGlossStrategy

class GlossStrategyFactory:
    @staticmethod
    def get_strategy(language_code: str) -> GlossStrategy:
        if language_code in ["de", "uk", "ru", "en", "it"]:
            return DefaultGlossStrategy(language_code)
        if language_code == "ja":
            return JapaneseGlossStrategy(language_code)
        elif language_code == "vi":
            return VietnameseGlossStrategy(language_code)
        elif language_code == "pt":
            return PortugueseGlossStrategy(language_code)
        else:
            return DefaultGlossStrategy(language_code)