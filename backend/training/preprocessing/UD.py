import re
import pandas as pd
from wasabi import msg
from typing import Union
from training.preprocessing.abstract import BasePreprocessor
from utils.functions import (
    load_glossing_rules
)

class UDPreprocessor(BasePreprocessor):
    def _process_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        # Clean text and gloss columns
        cleaned_texts = df[self.TEXT_COLUMN].map(self._clean_text)
        cleaned_glosses = df[self.GLOSS_COLUMN].map(self._clean_text)

        # Split by line and filter out blank lines, keeping only well-aligned rows
        texts, glosses = [], []
        for raw_text, raw_gloss in zip(cleaned_texts, cleaned_glosses):
            text_lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
            gloss_lines = [line.strip() for line in raw_gloss.split("\n") if line.strip()]
            if len(text_lines) != len(gloss_lines):
                msg.warn(
                    f"Skipped row due to line count mismatch: {len(text_lines)} texts vs {len(gloss_lines)} glosses"
                )
                self.logger.warning(
                    f"Skipped row: {len(text_lines)} texts vs {len(gloss_lines)} glosses"
                )
                continue
            texts.extend(text_lines)
            glosses.extend(gloss_lines)

        # Prepare rows list, comparing token counts not character counts
        rows = []
        for text, gloss in zip(texts, glosses):
            feats = self._map_gloss(gloss)
            tokens = text.split()  # split on whitespace to get tokens
            if len(tokens) != len(feats):
                msg.warn(
                    f"Token mismatch for text: '{text}' (num tokens={len(tokens)}, num feats={len(feats)})"
                )
                self.logger.warning(
                    f"Token mismatch: '{text}' (tokens={len(tokens)}, feats={len(feats)})"
                )
                continue
            rows.append({'text': tokens, 'UDfeats': feats})

        # Create DataFrame with correct columns even if empty
        if rows:
            new_df = pd.DataFrame(rows)
        else:
            new_df = pd.DataFrame(columns=['text', 'UDfeats'])

        # Drop rows where text is empty AND gloss list is empty
        mask = ~(
            (new_df['text'].apply(lambda lst: len(lst) == 0)) &
            (new_df['UDfeats'].apply(lambda lst: len(lst) == 0))
        )
        return new_df.loc[mask].reset_index(drop=True)

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
    
    def _map_gloss(self, gloss: str) -> list[str]:
        self.tokens_without_gloss = set()
        self.unknown_codes = set()
        self.LEIPZIG_GLOSSARY = load_glossing_rules("LEIPZIG_GLOSSARY.json")
        self.LEIPZIG2UD = {
            entry["leipzig"]: (entry["category"], key)
            for key, entry in self.LEIPZIG_GLOSSARY.items()
        }
        if not isinstance(gloss, str):
            return []
        feats = []
        for token in gloss.split():
            is_gloss = '.' in token or token.isupper() or any(c.isdigit() for c in token)
            if not is_gloss:
                feats.append('_')
                self.tokens_without_gloss.add(token)
                continue
            parts = [c.upper() for c in token.split('.') if c]
            if parts and parts[0].islower():
                parts.pop(0)
            mapped = []
            for code in parts:
                pair = self.LEIPZIG2UD.get(code)
                if pair:
                    mapped.append(f"{pair[0]}={pair[1]}")
                else:
                    self.unknown_codes.add(code)
            feats.append('|'.join(mapped) if mapped else '')
        return feats
    
    def _after_write(self):
        """
        Final cleanup after writing processed data:
        - Log any tokens without glosses and unknown codes.
        """
        self.logger.warning(f"Tokens without glosses: {self.tokens_without_gloss}")
        self.logger.warning(f"Unknown codes encountered: {self.unknown_codes}")