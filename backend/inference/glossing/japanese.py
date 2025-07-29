import re
import spacy
from pathlib import Path
from spacy.cli import download
from spacy.util import is_package

from utils.functions import load_glossing_rules
from inference.glossing.stanza import StanzaGlossingStrategy


LEIPZIG_GLOSSARY = load_glossing_rules("LEIPZIG_GLOSSARY.json")

class JapaneseGlossingStrategy(StanzaGlossingStrategy):
    """
    A glossing strategy that either uses a default spaCy model
    or a custom one in models/glossing/, plus optional translation.
    """

    def gloss(self, sentence: str) -> str:
        doc = self.nlp(sentence)
        out_tokens = []

        for token in doc:
            # passthrough bracketed/digits
            if re.search(r"[\(\[\]\)\d]", token.text):
                out_tokens.append(token.text)
                continue

            # get a normalized lemma
            lemma = token.lemma.lower()
            if not lemma:
                lemma = token.text.lower()

            lemma = lemma.replace(" ", ".")  # replace spaces with hyphens
            pos = token.upos
            if lemma == 'が':
                rule_feat = 'NOM'
            elif lemma == 'は':
                rule_feat = 'TOP'
            elif lemma == 'の':
                rule_feat = 'GEN'
            elif lemma == 'を':
                rule_feat = 'ACC'
            elif lemma == 'に':
                rule_feat = 'DAT'
            elif lemma == 'へ':
                rule_feat = 'ALL'
            elif lemma == 'から':
                rule_feat = 'ABL'
            elif lemma == 'で':
                rule_feat = 'INS'

            out_tokens.append(f"{lemma}.{pos}.{rule_feat}" if rule_feat else f"{lemma}-{pos}")


        return " ".join(out_tokens)
