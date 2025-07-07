import re
import sys
import stanza
from typing import List, Tuple, Dict
from inference.pii_identifier.abstract import PIIStrategy
import torch
from functools import wraps

_original_torch_load = torch.load

@wraps(_original_torch_load)
def _always_full_load(f, *args, **kwargs):
    kwargs.setdefault('weights_only', False)
    return _original_torch_load(f, *args, **kwargs)

torch.load = _always_full_load



class StanzaIdentifier(PIIStrategy):
    """
    Identifies and annotates Personally Identifiable Information (PII)
    in text using Stanza NER plus regex rules for structured identifiers.
    """

    # Regex patterns for other PII
    REGEX_PATTERNS: Dict[str, str] = {
        "EMAIL": r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
        "PHONE": r"(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{2,4}\)?[\s-]?)?\d{3,4}[\s-]?\d{3,4}",
        "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
        # add more patterns as needed
    }

    
    def load_model(self):
        """
        Initialize the Stanza pipeline for the given language.
        If the model is not downloaded, it will be fetched automatically.
        """
        try:
            stanza.download(self.lang)
        except Exception:
            print(f"Warning: Failed to download Stanza model for language '{self.lang}': {e}")

        try:
            self.nlp = stanza.Pipeline(lang=self.lang, processors='tokenize,ner')
            print(f"Stanza NER initialized for language: {self.lang}")
            print('nlp in identifier initialization', self.nlp)
        except Exception as e:
            print('error details', e)
            raise RuntimeError(f"Failed to initialize Stanza NER for language: {self.lang}. Please check if the language code is correct or if the model is available.")

    def identify_and_annotate(self, text: str) -> Tuple[List[Tuple[int, int, str, str]], str]:
        """
        Identify PII spans and return both the spans and an annotated text.

        Returns:
            spans: List of tuples (start_char, end_char, label, span_text)
            annotated_text: Original text with PII spans wrapped as [LABEL: span_text]
        """
        spans: List[Tuple[int, int, str, str]] = []
        if not self.nlp:
            return spans, text
        
        # 1) Stanza NER
        doc = self.nlp(text)
        for ent in doc.ents:
            if ent.type in ['PER', 'ORG', 'GPE', 'LOC', 'DATE']:
                spans.append((ent.start_char, ent.end_char, ent.type, ent.text))

        # 2) regex-based PII
        for label, pattern in self.REGEX_PATTERNS.items():
            for m in re.finditer(pattern, text):
                spans.append((m.start(), m.end(), label, m.group()))

        # sort & annotate
        spans = sorted(spans, key=lambda x: x[0])
        annotated_parts: List[str] = []
        last_idx = 0
        for start, end, label, span_text in spans:
            annotated_parts.append(text[last_idx:start])
            annotated_parts.append(f"[{label}: {text[start:end]}]")
            last_idx = end
        annotated_parts.append(text[last_idx:])

        annotated_text = ''.join(annotated_parts)
        return spans, annotated_text

# Example usage:
# identifier = PII_Identifier('en')\#
# spans, annotated = identifier.identify_and_annotate("Contact John Doe at john.doe@example.com on 2025-07-07.")
# print(annotated)
