import re
import spacy
from typing import List, Tuple, Dict
from spacy.cli import download as spacy_download
from importlib import util

class PII_Identifier:
    """
    Identifies and annotates Personally Identifiable Information (PII)
    in text using spaCy NER plus regex rules for structured identifiers.
    """

    # spaCy entity labels we care about
    SPACY_LABELS = {"PER", "ORG", "GPE", "LOC", "DATE"}

    # Regex patterns for other PII
    REGEX_PATTERNS: Dict[str, str] = {
        "EMAIL":   r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
        "PHONE":   r"(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{2,4}\)?[\s-]?)?\d{3,4}[\s-]?\d{3,4}",
        "SSN":     r"\b\d{3}-\d{2}-\d{4}\b",
        # add more patterns as needed
    }
    def __init__(self, lang: str):
        # Map of language codes to spaCy model names
        models = {
            'de': 'de_core_news_lg',
            'en': 'en_core_web_lg',
            'fr': 'fr_core_news_lg',
            'zh': 'zh_core_web_lg',
            'el': 'el_core_news_lg',
            'it': 'it_core_news_lg',
            'ja': 'ja_core_news_lg',
            'pt': 'pt_core_news_lg',
            'ro': 'ro_core_news_lg',
            'ru': 'ru_core_news_lg',
            'uk': 'uk_core_news_lg'
        }

        self.lang = lang
        model_name = models.get(lang)

        if not model_name:
            # No model defined for this language
            self.nlp = None
            return

        # Check if the model package is already installed
        if not util.find_spec(model_name):
            try:
                print(f"Model '{model_name}' not found. Downloading…")
                spacy_download(model_name)
            except Exception as e:
                print(f"Failed to download '{model_name}': {e}")
                self.nlp = None
                return

        # Try to load the model
        try:
            self.nlp = spacy.load(model_name)
        except Exception as e:
            print(f"Failed to load '{model_name}': {e}")
            self.nlp = None


    def identify_and_annotate(self, text: str):
        spans: List[Tuple[int,int,str,str]] = []
        doc = self.nlp(text)
        # 1) spaCy NER
        for ent in doc.ents:
            if ent.label_ in self.SPACY_LABELS:
                if ent.text != "Ellie" and ent.text != "Elli":
                    spans.append((ent.start_char, ent.end_char, ent.label_, ent.text))

        # 2) regex-based PII
        for label, pattern in self.REGEX_PATTERNS.items():
            for m in re.finditer(pattern, text):
                spans.append((m.start(), m.end(), label, m.group()))

        # sort & annotate
        spans = sorted(spans, key=lambda x: x[0])
        annotated = []
        last_idx = 0
        for start, end, label, span in spans:
            annotated.append(text[last_idx:start])
            annotated.append(f"[{label}: {text[start:end]}]")
            last_idx = end
        annotated.append(text[last_idx:])

        return spans, "".join(annotated)