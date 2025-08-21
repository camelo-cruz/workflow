import re
import spacy
from spacy.cli import download
from spacy.util import is_package
from utils.functions import load_glossing_rules
from inference.glossing.abstract import GlossingStrategy
from inference.translation.factory import TranslationStrategyFactory

LEIPZIG_GLOSSARY = load_glossing_rules("LEIPZIG_GLOSSARY.json")

class PortugueseGlossingStrategy(GlossingStrategy):
    def __init__(self, language_code: str):
        super().__init__(language_code)
        self.translation_strategy = TranslationStrategyFactory.get_strategy(language_code)
        self.nlp = self.load_model()

    def load_model(self):
        model_name = "pt_core_news_lg"
        if not is_package(model_name):
            print(f"{model_name} isn't installed—pulling it down now…")
            download(model_name)
        try:
            return spacy.load(model_name)
        except Exception as e:
            print(f"Error loading spaCy model {model_name}: {e}")
            raise

    def _clean_portuguese_sentence(self, glossed_sentence: str, lemmatized_sentence: str) -> str:
        """
        Apply Portuguese-specific adjustments to a glossed output.
        """
        glossed_tokens = glossed_sentence.split()
        lemmatized_words = lemmatized_sentence.split()
        wh_tags = {"que", "qual", "quem", "quando", "onde"}

        for wh in wh_tags:
            if wh in lemmatized_words:
                idx = lemmatized_words.index(wh)
                # Handle complementizer sequences "que que"
                if wh == "que" and idx + 1 < len(lemmatized_words) and lemmatized_words[idx + 1] == "que":
                    glossed_tokens[idx + 1] = "COMP"

                # Clean inflectional codes and map REL/IND to INT for wh-words
                token = glossed_tokens[idx]
                parts = token.split('-', 1)
                lemma = parts[0]
                feats = parts[1].split('-') if len(parts) > 1 else []

                # Remove gender/number specifications
                core_feats = [f for f in feats if f not in ("F", "M", "SG", "PL")]
                # Map REL and IND to INT (interrogative)
                #core_feats = ["INT" if f in ("REL", "IND") else f for f in core_feats]

                # Reconstruct cleaned token
                if core_feats:
                    glossed_tokens[idx] = lemma + '-' + '-'.join(core_feats)
                else:
                    glossed_tokens[idx] = lemma

        # Special case: drop determiner "o" before "que"
        if "o que" in lemmatized_sentence:
            words = lemmatized_words
            try:
                o_idx = words.index("o")
                if o_idx + 1 < len(words) and words[o_idx + 1] == "que":
                    del glossed_tokens[o_idx]
            except ValueError:
                pass

        # Normalize whitespace and stray dots
        output = ' '.join(glossed_tokens)
        output = re.sub(r"\s+", " ", output)
        output = re.sub(r"\.+", ".", output)
        return output.strip()

    def gloss(self, sentence: str) -> str:
        """
        Generate an interlinear gloss for a Portuguese sentence.
        """
        doc = self.nlp(sentence)
        gloss_tokens = []
        lemmas = []

        for token in doc:
            text = token.text
            # Passthrough digits and brackets unchanged
            if re.search(r"[()\[\]\d]", text):
                gloss_tokens.append(text)
                lemmas.append(text)
                continue

            lemma = token.lemma_.lower() or text.lower()
            lemmas.append(lemma)

            # Optional translation (commented out)
            #if self.translation_strategy:
            #    translated_lemma = self.translation_strategy.translate(text=lemma)
            #    if not translated_lemma:
            #        translated_lemma = lemma

            translated_lemma = lemma
            lemma = translated_lemma.replace(" ", ".")

            feats = self.map_morph_to_leipzig(token.morph.to_dict())
            if feats:
                gloss_tokens.append(f"{lemma}.{feats}")
            else:
                gloss_tokens.append(lemma)

        glossed_sentence = ' '.join(gloss_tokens)
        lemmatized_sentence = ' '.join(lemmas)
        sentence_to_return = self._clean_portuguese_sentence(glossed_sentence, lemmatized_sentence)
        print(f"Glossed sentence: {sentence_to_return}")
        return sentence_to_return
