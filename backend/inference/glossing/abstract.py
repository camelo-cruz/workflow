from abc import ABC, abstractmethod
from wasabi import msg
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
        return entry.get("leipzig", val.upper() if val else val)

    def UD2LEIPZIG(self, morph):
        # Map all morphological features via LEIPZIG_GLOSSARY in defined order
        features_in_order = [
            #Defined order
            "PronType", "Definite", "Gender", "Person", "Number", "Case",

            # Lexical Features
            "NumType", "Other", #"Poss", "Reflex",
            "Abbr",  "ExtPos", "Clusivity", #"Typo", "Foreign",
            # Nominal Features
            "Animacy", "NounClass", 
             "Deixis", "DeixisRef", "Degree",
            # Verbal Features
            "VerbForm", "Mood", "Tense", "Aspect", "Voice", 
            "Evident", "Polarity", "Polite",
        ]
        glossary_categories = {v["category"] for v in LEIPZIG_GLOSSARY.values()}
        missing_categories = glossary_categories - set(features_in_order)
        if missing_categories:
            message = f"Missing categories in features_in_order" \
                f"check LEIPZIG_GLOSSARY and abstract Glossing strategy to fix: {sorted(missing_categories)}"
            raise ValueError(message)

        mapped_parts = []
        seen = set()

        # Add in preferred order
        for feature in features_in_order:
            value = self.map_leipzig(morph, feature)
            if value and value != "None":
                mapped_parts.append(value)
            seen.add(feature)

        # Add any other features from morph that weren’t in the preferred order
        for feature, val in morph.items():
            if feature not in seen:
                # If it's in the glossary, map it
                mapped = self.map_leipzig(morph, feature)
                if mapped and mapped != "None":
                    mapped_parts.append(mapped)
                else:
                    # Otherwise, fall back to "Feature=Value"
                    mapped_parts.append(f"{feature}={val}")

        return "-".join(mapped_parts)

    