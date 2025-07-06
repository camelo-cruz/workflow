import re
import spacy
from typing import List, Tuple, Dict

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
        self.lang = lang
        if self.lang == "de":
            self.nlp = spacy.load("de_core_news_lg")
        elif self.lang == "en":
            self.nlp = spacy.load("en_core_web_lg")
        else:
            self.nlp = None

    def identify_and_annotate(self, text: str):
        spans: List[Tuple[int,int,str,str]] = []
        doc = self.nlp(text)
        # 1) spaCy NER
        for ent in doc.ents:
            if ent.label_ in self.SPACY_LABELS:
                if ent.text != "Ellie":
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