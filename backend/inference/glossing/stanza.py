import stanza
import re
import torch

from utils.functions import load_glossing_rules
from inference.glossing.abstract import GlossingStrategy
from inference.translation.factory import TranslationStrategyFactory

LEIPZIG_GLOSSARY = load_glossing_rules("LEIPZIG_GLOSSARY.json")

class StanzaGlossingStrategy(GlossingStrategy):
    """
    A glossing strategy that either uses a default stanza model
    or a custom one in models/glossing/, plus optional translation.
    """

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
        _orig = torch.load
        torch.load = lambda f, *a, **k: _orig(f, *a, weights_only=False, **k)
        self.nlp = stanza.Pipeline(
            self.language_code,
            processors="tokenize,pos,lemma",
            use_gpu=True
        )
        # put it back
        torch.load = _orig
    
    def parse_stanza_feats(self, feats_str):
        if not feats_str:
            return {}
        return dict(kv.split("=") for kv in feats_str.split("|") if kv and "=" in kv)

    def gloss(self, sentence: str) -> str:
        doc = self.nlp(sentence)
        out_tokens = []
        for sent in doc.sentences:
            for token in sent.words:
                # passthrough bracketed/digits
                if re.search(r"[\(\[\]\)\d]", token.text):
                    out_tokens.append(token.text)
                    continue

                # get a normalized lemma
                lemma = token.lemma.lower()
                if not lemma:
                    lemma = token.text.lower()

                # optional translation
                if self.translation_strategy:
                    lemma = self.translation_strategy.translate(text=lemma)
                    lemma = lemma.replace(" ", "-")  # replace spaces with hyphens
            
                # build the Leipzig gloss
                feats_dict = self.parse_stanza_feats(token.feats)
                gloss_feats = self.UD2LEIPZIG(feats_dict)
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
            "Abbr", "Typo", "Foreign", "ExtPos", "Clusivity",
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

        glossed_word = ".".join(mapped_parts)

        return glossed_word if glossed_word else ""
