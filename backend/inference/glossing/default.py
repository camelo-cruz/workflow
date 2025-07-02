import re
import spacy

from spacy.cli import download
from spacy.util import is_package
from inference.glossing.abstract import GlossingStrategy
from inference.translation.factory import TranslationStrategyFactory

class DefaultGlossingStrategy(GlossingStrategy):
    def __init__(self, language_code: str):
        super().__init__(language_code)
        self.nlp = None
        self.translation_strategy = TranslationStrategyFactory.get_strategy(language_code)
        self.translation_strategy.load_model()

    def load_model(self):
        models = {
            "de": "de_dep_news_trf",
            "uk": "uk_core_news_trf",
            "ru": "ru_core_news_lg",
            "en": "en_core_web_trf",
            "it": "it_core_news_lg",
        }
        if self.language_code not in models:
            raise ValueError(f"No default spaCy model registered for {self.language_code!r}")
        model_name = models[self.language_code]
        if not is_package(model_name):
            print(f"{model_name} isn’t installed—pulling it down now…")
            download(model_name)
        self.nlp = spacy.load(model_name)

    def gloss(self, sentence: str) -> str:
        doc = self.nlp(sentence)
        glossed_sentence = ""
        for token in doc:
            # skip bracketed/digit tokens
            if re.search(r"[\(\[\]\)\d]", token.text):
                glossed_sentence += token.text + " "
            else:
                lemma = token.lemma_
                morph = token.morph.to_dict()

                # Translate lemma → English
                translated_lemma = self.translation_strategy.translate(text=lemma)
                if isinstance(translated_lemma, str):
                    translated_lemma = translated_lemma.lower().replace(" ", "-")

                # Map morphological features via LEIPZIG_GLOSSARY
                arttype  = self.map_leipzig(morph, "PronType")
                definite = self.map_leipzig(morph, "Definite")
                person   = self.map_leipzig(morph, "Person")
                number   = self.map_leipzig(morph, "Number")
                gender   = self.map_leipzig(morph, "Gender")
                case     = self.map_leipzig(morph, "Case")
                tense    = self.map_leipzig(morph, "Tense")
                mood     = self.map_leipzig(morph, "Mood")

                glossed_word = (
                    f"{translated_lemma}.{arttype}.{definite}."
                    f"{gender}.{person}.{number}.{case}.{tense}.{mood}"
                )
                # strip any “None” bits
                glossed_word = re.sub(r"(?:\.|-|\b)None", "", glossed_word)
                glossed_sentence += glossed_word + " "
        return glossed_sentence.strip()


if __name__ == "__main__":
    glossing_strategy = DefaultGlossingStrategy(language_code="de")
    glossing_strategy.load_model()
    sentence = "Ich sage dir, dass er ein guter Lehrer ist."
    glossed_sentence = glossing_strategy.gloss(sentence)
    print(glossed_sentence)