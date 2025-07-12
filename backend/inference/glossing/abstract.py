from abc import ABC, abstractmethod
from utils.functions import load_glossing_rules
from inference.translation.factory import TranslationStrategyFactory

LEIPZIG_GLOSSARY = load_glossing_rules("LEIPZIG_GLOSSARY.json")

class GlossingStrategy(ABC):
    """
    Abstract base class for glossing strategies.
    Subclasses must implement:
      - load_model()
      - gloss_sentence(sentence: str) -> str
    """
    def __init__(self, language_code: str, glossingModel: str = None, translationModel: str = None):
        self.language_code = language_code
        self.glossing_model = glossingModel
        self.nlp = None

        try:
            self.translation_strategy = TranslationStrategyFactory.get_strategy(
                language_code=language_code,
                translationModel=translationModel
            )
            self.translation_strategy.load_model()
        except Exception as e:
            print(f"Warning: could not load translation model: {e}")
            self.translation_strategy = None
        self.load_model()

    @abstractmethod
    def load_model(self):
        raise NotImplementedError("Subclasses must implement load_model()")

    @abstractmethod
    def gloss(self, sentence: str) -> str:
        raise NotImplementedError("Subclasses must implement gloss_sentence()")
    
    @staticmethod
    def map_leipzig(morph, feat):
        val = morph.get(feat)
        entry = LEIPZIG_GLOSSARY.get(val, {})
        return entry.get("leipzig", val)
    
    def UD2LEIPZIG(self, morph):
        # Map all morphological features via LEIPZIG_GLOSSARY in defined order
        features_in_order = [
            # Lexical Features
            "PronType", "NumType", "Other", #"Poss", "Reflex",
            "Abbr",  "ExtPos", "Clusivity", #"Typo", "Foreign",
            # Verbal Features
            "VerbForm", "Mood", "Tense", "Aspect", "Voice", 
            "Evident", "Polarity", "Person", "Polite",
            # Nominal Features
            "Number", "Gender", "Animacy", "NounClass", "Case", 
            "Definite", "Deixis", "DeixisRef", "Degree",
        ]

        mapped_parts = []
        for feature in features_in_order:
            value = self.map_leipzig(morph, feature)
            if value and value != "None":
                mapped_parts.append(value)

        mapped_features = ".".join(mapped_parts)

        return mapped_features

    