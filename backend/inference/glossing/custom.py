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

    def load_model(self, model_name: str):
        model_name = model_name
        if model_name is None:
            raise ValueError("Model name must be provided for loading the custom glossing model.")
        model_path = Path("models/glossing", model_name)
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
                translated_lemma = self.translation_strategy.translate(text=lemma)
                print(f"Token: {token.text}, translated_lemma: {translated_lemma}, Morph: {morph}")
                if isinstance(lemma, str):
                    lemma = lemma.lower().replace(" ", "-")
                    #lemma = self.translation_strategy.translate(text=lemma)
                    #print(f"Translated lemma: {lemma}")

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
                    f"{lemma}.{arttype}.{definite}."
                    f"{gender}.{person}.{number}.{case}.{tense}.{mood}"
                )
                # strip any “None” bits
                glossed_word = re.sub(r"(?:\.|-|\b)None", "", glossed_word)
                glossed_sentence += glossed_word + " "
        return glossed_sentence.strip()

if __name__ == "__main__":
    glossing_strategy = CustomGlossingStrategy(language_code="yo")
    glossing_strategy.load_model(model_name="yo_H_custom_glossing")
    sentence = "Ehoro tí ó ń jẹun (ni ó pa àwọ̀ dà"
    glossed_sentence = glossing_strategy.gloss(sentence)
    print(glossed_sentence)
