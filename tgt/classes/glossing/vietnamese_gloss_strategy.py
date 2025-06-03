import re
import stanza
import spacy_stanza
from spacy.cli import download
from spacy.util import is_package
from .gloss_strategy import GlossStrategy
from ...utils.functions import load_glossing_rules

from deep_translator import GoogleTranslator
class VietnameseGlossStrategy(GlossStrategy):

    def __init__(self, language_code: str):
        super().__init__(language_code)
        self.nlp = None
        self.VI_OVERRIDES = load_glossing_rules("vietnamese.json")

    def load_model(self):
        stanza.download(self.language_code)
        self.nlp = spacy_stanza.load_pipeline(self.language_code)

    def clean_vietnamese_lemma(self, lemma: str):
        return self.VI_OVERRIDES.get(lemma, None)

    def gloss_sentence(self, sentence: str) -> str:
        doc = self.nlp(sentence)
        glossed = ""
        for token in doc: 
            if re.search(r"[\(\[\]\)\d]", token.text):
                glossed += token.text
            else:
                lemma = token.lemma_.lower()
                translated = GoogleTranslator(source="vi", target="en").translate(text=lemma)
                override = self.clean_vietnamese_lemma(lemma)
                if override:
                    lemma_override, pos_override = override
                    glossed_word = f"{lemma_override}.{pos_override}"
                else:
                    glossed_word = f"{translated}.{token.pos_.upper()}.{token.dep_.upper()}"
                glossed_word = re.sub(r"(?:\.|-|\b)None", "", glossed_word)
                glossed += glossed_word + " "
        return glossed.strip()