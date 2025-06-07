import re
import spacy
from spacy.cli import download
from spacy.util import is_package
from utils.functions import load_glossing_rules
from deep_translator import GoogleTranslator
from .abstract import GlossingStrategy

LEIPZIG_GLOSSARY = load_glossing_rules("LEIPZIG_GLOSSARY")


class PortugueseGlossingStrategy(GlossingStrategy):
    def __init__(self, language_code: str):
        super().__init__(language_code)

    def load_model(self):
        model_name = "pt_core_news_lg"
        if not is_package(model_name):
            print(f"{model_name} isn’t installed—pulling it down now…")
            download(model_name)
        self.nlp = spacy.load(model_name)

    def _clean_portuguese_sentence(self, glossed_sentence: str, lemmatized_sentence: str) -> str:
        """
        The same logic you had before, factored out into a helper.
        """
        glossed_tokens = glossed_sentence.split()
        lemmatized_words = lemmatized_sentence.split()
        wh_questions = ["que", "qual", "quem", "quando", "onde"]

        for wh in wh_questions:
            if wh in lemmatized_words:
                wh_idx = lemmatized_words.index(wh)
                if wh_idx + 1 < len(lemmatized_words) and lemmatized_words[wh_idx + 1] == "que":
                    glossed_tokens[wh_idx + 1] = "COMP"
                if wh in ("quem", "que", "qual") and wh_idx < len(glossed_tokens) and wh_idx < 2:
                    cleaned = glossed_tokens[wh_idx]
                    cleaned = cleaned.replace("F", "").replace("M", "")
                    cleaned = cleaned.replace("SG", "").replace("PL", "")
                    cleaned = cleaned.replace("REL", "INT").replace("IND", "INT")
                    if wh == "qual":
                        cleaned = cleaned.replace("M", "INT")
                    glossed_tokens[wh_idx] = cleaned

        if "o que" in lemmatized_sentence:
            words = lemmatized_words
            if "o" in words:
                o_idx = words.index("o")
                if o_idx + 1 < len(words) and words[o_idx + 1] == "que":
                    del glossed_tokens[o_idx]

        out = " ".join(glossed_tokens)
        out = re.sub(r"\s+", " ", out)
        out = re.sub(r"\. +", " ", out)
        return out.strip()

    def gloss(self, sentence: str) -> str:
        # First invoke DefaultGlossStrategy’s logic to get an “uncleaned” gloss
        doc = self.nlp(sentence)
        glossed_sentence = ""
        lemmatized_sentence = ""

        for token in doc:
            if re.search(r"[\(\[\]\)\d]", token.text):
                glossed_sentence += token.text + " "
                lemmatized_sentence += token.text + " "
            else:
                lemma = token.lemma_
                morph = token.morph.to_dict()

                translated_lemma = GoogleTranslator(source="pt", target="en").translate(text=lemma)
                if isinstance(translated_lemma, str):
                    translated_lemma = translated_lemma.lower().replace(" ", "-")

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
                glossed_word = re.sub(r"(?:\.|-|\b)None", "", glossed_word)
                glossed_sentence += glossed_word + " "
                lemmatized_sentence += lemma + " "

        glossed_sentence = glossed_sentence.strip()
        lemmatized_sentence = lemmatized_sentence.strip()

        # Now apply Portuguese-specific cleaning
        glossed_sentence = self._clean_portuguese_sentence(glossed_sentence, lemmatized_sentence)
        return glossed_sentence