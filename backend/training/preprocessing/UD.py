import re
import pandas as pd
from typing import Union
from training.preprocessing.abstract import AbstractPreprocessor

class UDPreprocessor(AbstractPreprocessor):
    def _process_dataframe(self, df: pd.DataFrame):
        pass
    
    def _clean_text(self, text: Union[str, float]) -> str:
        """
        Clean and normalize text fields:
        - Collapse ellipses, replace commas, strip punctuation and digits,
            remove bracketed content, and normalize whitespace.
        """
        if not isinstance(text, str):
            return ""

        # Replace double dots, standardize commas, remove outer dots
        text = text.replace('..', '.').replace(',', ' PUNCT ')
        text = text.strip().strip('.')

        # Remove bracket characters and leading digits
        text = re.sub(r"[\[\]\(\)\{\}01-9]+", "", text)

        # Normalize grammatical SG/PL markers
        text = re.sub(r"\b(\d)(SG|PL)\b", r"\1.\2", text)

        # Collapse whitespace
        text = re.sub(r"\s+", " ", text)
        return text.strip()