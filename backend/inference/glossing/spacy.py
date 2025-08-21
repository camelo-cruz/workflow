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
        if self.glossing_model:
            models_dir = Path(__file__).resolve().parents[2] / "models/glossing"
            model_dir = models_dir / (self.glossing_model)
            print(f"Loading custom glossing model from {model_dir}")
            if not model_dir.exists():
                raise ValueError(f"Custom glossing model not found at {model_dir}")
            self.nlp = spacy.load(model_dir)
        elif self.language_code in self.DEFAULT_SPACY:
            pkg = self.DEFAULT_SPACY[self.language_code]
            if not is_package(pkg):
                print(f"{pkg} not found — downloading…")
                download(pkg)
            self.nlp = spacy.load(pkg)

        else:
            raise ValueError("No glossing model specified or available for this language.")

    def gloss(self, text: str, keep_punct: bool = True, debug: bool = True) -> str:
        """
        Build a Leipzig-style gloss string from model predictions.
        - Preserves newline boundaries: gloss each line independently.
        - Preserves original whitespace via token.whitespace_.
        - Avoids double hyphens by joining parts safely.
        - Passthrough for punctuation/brackets/numbers (configurable).
        """
        lines = text.splitlines()  # keep exact user-provided line breaks
        glossed_lines = []

        for line in lines:
            if not line.strip():
                glossed_lines.append("")  # preserve empty lines
                continue

            doc = self.nlp(line)
            out_parts = []

            if debug:
                print(f"Processing line: {line!r}")

            for tok in doc:
                # keep whitespace handling consistent with the original text
                ws = tok.whitespace_

                # passthrough rules (match your training "_ for punct" behavior if you prefer)
                if keep_punct and (tok.is_punct or tok.like_num or re.search(r"[\(\)\[\]]", tok.text)):
                    out_parts.append(tok.text + ws)
                    continue

                # lemma fallback + normalization
                lemma = (tok.lemma_ or tok.text).lower()
                lemma = lemma.strip().replace(" ", "-")  # multiword lemmas → hyphen-joined

                # map UD → Leipzig (you already have this util)
                # token.morph.to_dict() returns {'Case': 'Nom', 'Number': 'Sing', ...} (may be empty)
                ud = tok.morph.to_dict()
                leipzig = self.map_morph_to_leipzig(ud)  # should return a string like "PRO-3-SG-NOM" or ""

                if debug:
                    print(f"TOK: {tok.text:<15} LEMMA: {lemma:<15} MORPH: {tok.morph}  →  {leipzig}\n")

                # safe join to avoid "--"
                piece = "-".join([p for p in (lemma, leipzig) if p])
                out_parts.append(piece + ws)

            glossed_lines.append("".join(out_parts).rstrip())

        return "\n".join(glossed_lines)