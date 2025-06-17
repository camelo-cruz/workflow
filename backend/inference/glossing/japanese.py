import spacy
from spacy.cli import download
from spacy.util import is_package
from inference.glossing.abstract import GlossingStrategy

class JapaneseGlossingStrategy(GlossingStrategy):
    def __init__(self, language_code: str):
        super().__init__(language_code)
        self.nlp = None

    def load_model(self):
        model_name = "ja_core_news_trf"
        if not is_package(model_name):
            print(f"{model_name} isn’t installed—pulling it down now…")
            download(model_name)
        self.nlp = spacy.load(model_name)

    def gloss(self, sentence: str) -> str:
        doc = self.nlp(sentence)
        glossed = ""
        for token in doc:
            if token.pos_ != "PUNCT":
                glossed += f"{token.text}.{token.pos_}.{token.dep_} "
        return glossed.strip()