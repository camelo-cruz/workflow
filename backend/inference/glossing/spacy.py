import re
import spacy
from pathlib import Path
from spacy.cli import download
from spacy.util import is_package

from utils.functions import load_glossing_rules
from inference.glossing.abstract import GlossingStrategy
from inference.translation.factory import TranslationStrategyFactory

LEIPZIG_GLOSSARY = load_glossing_rules("LEIPZIG_GLOSSARY.json")

class SpaCyGlossingStrategy(GlossingStrategy):
    """
    A glossing strategy that either uses a default spaCy model
    or a custom one in models/glossing/, plus optional translation.
    """
    # spaCy model names for each language
    DEFAULT_SPACY = {
            'de': 'de_core_news_lg',
            'en': 'en_core_web_lg',
            'fr': 'fr_core_news_lg',
            'zh': 'zh_core_web_lg',
            'el': 'el_core_news_lg',
            'it': 'it_core_news_lg',
            'ja': 'ja_core_news_lg',
            'pt': 'pt_core_news_lg',
            'ro': 'ro_core_news_lg',
            'ru': 'ru_core_news_lg',
            'uk': 'uk_core_news_lg'
        }

    def __init__(self,
                 language_code: str,
                 glossingModel: str = None,
                 translationModel: str = None):
        super().__init__(language_code)
        self.glossing_model = glossingModel
        self.nlp = None

        # load translation strategy if requested
        try:
            self.translation_strategy = TranslationStrategyFactory.get_strategy(
                language_code=language_code,
                translationModel=translationModel
            )
            self.translation_strategy.load_model()
        except Exception as e:
            print(f"Warning: could not load translation model: {e}")
            self.translation_strategy = None

    def load_model(self):
        """
        - If glossing_model is one of the DEFAULT_SPACY keys, load that spaCy package.
        - Else assume it's a custom subfolder under models/glossing/.
        """

        if self.language_code in self.DEFAULT_SPACY:
            pkg = self.DEFAULT_SPACY[self.language_code]
            if not is_package(pkg):
                print(f"{pkg} not found — downloading…")
                download(pkg)
            self.nlp = spacy.load(pkg)

        elif self.glossing_model:
            model_dir = Path("models/glossing") / (self.glossing_model)
            if not model_dir.exists():
                raise ValueError(f"Custom glossing model not found at {model_dir}")
            self.nlp = spacy.load(model_dir)
        else:
            raise ValueError("No glossing model specified or available for this language.")

    def gloss(self, sentence: str) -> str:
        doc = self.nlp(sentence)
        out_tokens = []

        for token in doc:
            # passthrough bracketed/digits
            if re.search(r"[\(\[\]\)\d]", token.text):
                out_tokens.append(token.text)
                continue

            # get a normalized lemma
            lemma = token.lemma_.lower()
            if not lemma:
                lemma = token.text.lower()

            # optional translation
            if self.translation_strategy:
                lemma = self.translation_strategy.translate(text=lemma)
                lemma = lemma.replace(" ", "-")  # replace spaces with hyphens

            # build the Leipzig gloss
            gloss_feats = self.UD2LEIPZIG(token.morph.to_dict())
            if gloss_feats:
                out_tokens.append(f"{lemma}.{gloss_feats}")
            else:
                out_tokens.append(lemma)

        return " ".join(out_tokens)
    
    @staticmethod
    def map_leipzig(morph, feat):
        val = morph.get(feat)
        entry = LEIPZIG_GLOSSARY.get(val, {})
        return entry.get("leipzig", val)
    
    def UD2LEIPZIG(self, morph):
        # Map all morphological features via LEIPZIG_GLOSSARY in defined order
        features_in_order = [
            # Lexical Features
            "PronType", "NumType", "Poss", "Reflex", "Other", 
            "Abbr", "ExtPos", "Clusivity", #"Typo", "Foreign",
            # Verbal Features
            "VerbForm", "Mood", "Tense", "Aspect", "Voice", 
            "Evident", "Polarity", "Person", "Polite"
            # Nominal Features
            "Number", "Gender", "Animacy", "NounClass", "Case", 
            "Definite", "Deixis", "DeixisRef", "Degree",
        ]

        mapped_parts = []
        for feature in features_in_order:
            value = self.map_leipzig(morph, feature)
            if value and value != "None":
                mapped_parts.append(value)

        glossed_word = ".".join(mapped_parts)

        return glossed_word if glossed_word else ""
