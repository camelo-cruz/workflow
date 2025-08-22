# --- abstract.py (or wherever GlossingStrategy lives) ---
import re
from abc import ABC, abstractmethod
from utils.functions import load_glossing_rules
from inference.translation.factory import TranslationStrategyFactory

LEIPZIG_GLOSSARY = load_glossing_rules("LEIPZIG_GLOSSARY.json")

# (category, UD) -> Leipzig
UD2LEIPZIG_MAP = {
    (v["category"], v["UD"]): k
    for k, v in LEIPZIG_GLOSSARY.items()
    if "category" in v and "UD" in v
}

GLOSSARY_CATEGORIES = {v["category"] for v in LEIPZIG_GLOSSARY.values() if "category" in v}

class GlossingStrategy(ABC):
    def __init__(self, language_code: str, glossingModel: str = None, translationModel: str = None):
        self.language_code = language_code
        self.glossing_model = glossingModel
        self.nlp = None
        try:
            self.translation_strategy = TranslationStrategyFactory.get_strategy(
                language_code=language_code, translationModel=translationModel
            )
            self.translation_strategy.load_model()
        except Exception as e:
            print(f"Warning: could not load translation model: {e}")
            self.translation_strategy = None
        self.load_model()

    @abstractmethod
    def load_model(self): ...
    @abstractmethod
    def gloss(self, sentence: str) -> str: ...

    # ---------- Leipzig mapping helpers ----------
    @staticmethod
    def _map_one_atom(category: str, ud_val_atom: str) -> str:
        """Map ONE UD atom (no commas) for a given category to Leipzig; fallback to upper."""
        return UD2LEIPZIG_MAP.get((category, ud_val_atom), ud_val_atom.upper())

    @staticmethod
    def map_feature(category: str, ud_val: str | None) -> str | None:
        """
        Map a SINGLE UD feature value (possibly comma-separated) to Leipzig.
        Handles exact combined matches first (e.g., Case='Acc,Dat,Nom'), else per-atom join with '/'.
        """
        if not ud_val or ud_val == "None":
            return None

        # exact combined value (e.g., ('Case','Acc,Dat,Nom'))
        code = UD2LEIPZIG_MAP.get((category, ud_val))
        if code:
            return code

        # comma-separated atoms
        if "," in ud_val:
            atoms = [a.strip() for a in ud_val.split(",") if a.strip()]
            mapped = [GlossingStrategy._map_one_atom(category, a) for a in atoms]
            return "/".join(mapped)

        # single atom
        return GlossingStrategy._map_one_atom(category, ud_val)

    def map_morph_to_leipzig(self, morph: dict) -> str:
        """
        Convert a whole spaCy morph dict (e.g., {'Case':'Nom','Gender':'Masc','Number':'Sing'})
        into a Leipzig string (e.g., 'M-SG-NOM') using a stable feature order.
        """
        features_in_order = [
            # Core order
            "PronType", "Definite", "Gender", "Person", "Number", "Case",
            # Lexical
            "NumType", "Other", "Abbr", "ExtPos", "Clusivity",
            # Nominal
            "Animacy", "NounClass", "Deixis", "DeixisRef", "Degree",
            # Verbal
            "VerbForm", "Mood", "Tense", "Aspect", "Voice",
            "Evident", "Polarity", "Polite", "Foreign", "Abbr", "Typo",
            "Poss"
        ]
        # sanity check (optional)
        missing = GLOSSARY_CATEGORIES - set(features_in_order)
        if missing:
            raise ValueError(
                f"Missing categories in features_in_order: {sorted(missing)} "
                f"(update order or glossary)"
            )

        parts = []
        seen = set()

        for cat in features_in_order:
            val = morph.get(cat)
            code = self.map_feature(cat, val)
            if code:
                parts.append(code)
            seen.add(cat)

        # include any remaining features (rare)
        for cat, val in morph.items():
            if cat in seen:
                continue
            code = self.map_feature(cat, val)
            if code:
                parts.append(code)
            else:
                # fallback: keep raw for debugging visibility
                parts.append(f"{cat}={val}")

        return "-".join(parts)
