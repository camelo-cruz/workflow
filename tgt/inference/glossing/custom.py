import re
import spacy

from pathlib import Path
from utils.functions import load_glossing_rules
from inference.glossing.abstract import GlossingStrategy
from inference.translation.factory import TranslationStrategyFactory


LEIPZIG_GLOSSARY = load_glossing_rules("LEIPZIG_GLOSSARY.json")

class CustomGlossingStrategy(GlossingStrategy):
    def __init__(self, language_code: str):
        super().__init__(language_code)
        self.nlp = None
        self.translation_strategy = TranslationStrategyFactory.get_strategy(language_code)
        self.translation_strategy.load_model()

    def load_model(self, model_name: str = None):
        model_name = 'de_dep_news_trf_custom_glossing'
        if model_name is None:
            raise ValueError("Model name must be provided for loading the custom glossing model.")
        model_path = Path("training", "glossing", "models", model_name)
        self.nlp = spacy.load(model_path)
        
    def gloss(self, sentence: str) -> str:
        doc = self.nlp(sentence)
        glossed_sentence = ""
        for token in doc:
            # skip bracketed/digit tokens
            if re.search(r"[\(\[\]\)\d]", token.text):
                glossed_sentence += token.text + " "
            else:
                lemma = token.text
                morph = token.morph.to_dict()

                # Translate lemma → English
                #translated_lemma = self.translation_strategy.translate(text=lemma)
                if isinstance(lemma, str):
                    lemma = lemma.lower().replace(" ", "-")

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
                    f"{lemma}.{arttype}.{definite}."
                    f"{gender}.{person}.{number}.{case}.{tense}.{mood}"
                )
                # strip any “None” bits
                glossed_word = re.sub(r"(?:\.|-|\b)None", "", glossed_word)
                glossed_sentence += glossed_word + " "
        return glossed_sentence.strip()

if __name__ == "__main__":
    glossing_strategy = CustomGlossingStrategy(language_code="de")
    glossing_strategy.load_model()
    sentence = "Ich sage dir, dass er ein guter Lehrer ist."
    glossed_sentence = glossing_strategy.gloss(sentence)
    print(glossed_sentence)
