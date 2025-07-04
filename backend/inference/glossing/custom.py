import re
import spacy

from pathlib import Path
from utils.functions import load_glossing_rules
from inference.glossing.abstract import GlossingStrategy
from inference.translation.factory import TranslationStrategyFactory


LEIPZIG_GLOSSARY = load_glossing_rules("LEIPZIG_GLOSSARY.json")

class CustomGlossingStrategy(GlossingStrategy):
    def __init__(self, language_code: str, glossingModel: str, translationModel: str = None):
        super().__init__(language_code)
        self.nlp = None
        self.glossingModel = glossingModel
        try:
            self.translation_strategy = TranslationStrategyFactory.get_strategy(
                language_code=language_code, 
                translationModel=translationModel
            )
            self.translation_strategy.load_model()
        except Exception as e:
            print(f"Error loading translation strategy: {e}")
            self.translation_strategy = None

    def load_model(self):
        model_path = Path("models/glossing", self.glossingModel)
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
               
                if isinstance(lemma, str):
                    lemma = lemma.lower().replace(" ", "-")
                    if self.translation_strategy:
                        translated_lemma = self.translation_strategy.translate(text=lemma)[0]
                    else:
                        translated_lemma = None

                    lemma = translated_lemma if translated_lemma else lemma

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
    glossing_strategy = CustomGlossingStrategy(language_code="de", 
                                               custom_glossing_mode="de_H_custom_glossing")
    glossing_strategy.load_model()
    sentence = "Das ist ein Test"
    glossed_sentence = glossing_strategy.gloss(sentence)
    print(glossed_sentence)
