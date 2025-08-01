import re
import spacy
from pathlib import Path
from spacy.cli import download
from spacy.util import is_package

from utils.functions import load_glossing_rules
from inference.glossing.abstract import GlossingStrategy


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
            models_dir = Path(__file__).resolve().parents[2] / "models/glossing"
            model_dir = models_dir / (self.glossing_model)
            print(f"Loading custom glossing model from {model_dir}")
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

            lemma = lemma.replace(" ", ".")  # replace spaces with hyphens

            print(token.morph)
            gloss_feats = self.UD2LEIPZIG(token.morph.to_dict())
            if gloss_feats:
                out_tokens.append(f"{lemma}-{gloss_feats}")
            else:
                out_tokens.append(lemma)

        glossed_text = " ".join(out_tokens)
        print(f"Glossed text: {glossed_text}")  # Debug output
        return glossed_text