import re
import spacy

from deep_translator import GoogleTranslator
from spacy.cli import download
from spacy.util import is_package
from utils.functions import load_glossing_rules
from .gloss_strategy import GlossStrategy


LEIPZIG_GLOSSARY = load_glossing_rules("LEIPZIG_GLOSSARY")

class DefaultGlossStrategy(GlossStrategy):
    def __init__(self, language_code: str):
        super().__init__(language_code)
        self.nlp = None

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

    def gloss_sentence(self, sentence: str) -> str:
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
                translated_lemma = GoogleTranslator(source=self.language_code, target="en").translate(text=lemma)
                if isinstance(translated_lemma, str):
                    translated_lemma = translated_lemma.lower().replace(" ", "-")

                # Map morphological features via LEIPZIG_GLOSSARY
                arttype = LEIPZIG_GLOSSARY.get(morph.get("PronType"), morph.get("PronType"))
                definite = LEIPZIG_GLOSSARY.get(morph.get("Definite"), morph.get("Definite"))
                person = LEIPZIG_GLOSSARY.get(morph.get("Person"), morph.get("Person"))
                number = LEIPZIG_GLOSSARY.get(morph.get("Number"), morph.get("Number"))
                gender = LEIPZIG_GLOSSARY.get(morph.get("Gender"), morph.get("Gender"))
                case   = LEIPZIG_GLOSSARY.get(morph.get("Case"), morph.get("Case"))
                tense  = LEIPZIG_GLOSSARY.get(morph.get("Tense"), morph.get("Tense"))
                mood   = LEIPZIG_GLOSSARY.get(morph.get("Mood"), morph.get("Mood"))

                glossed_word = (
                    f"{translated_lemma}.{arttype}.{definite}."
                    f"{gender}.{person}.{number}.{case}.{tense}.{mood}"
                )
                # strip any “None” bits
                glossed_word = re.sub(r"(?:\.|-|\b)None", "", glossed_word)
                glossed_sentence += glossed_word + " "
        return glossed_sentence.strip()
