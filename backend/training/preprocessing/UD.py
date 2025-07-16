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
        rows = []
        # Iterate through each original row to preserve raw text and translation
        for idx, row in df.iterrows():
            raw_text = str(row.get(self.TEXT_COLUMN, ""))
            raw_translation = str(row.get(self.TRANSLATION_COLUMN, ""))
            raw_gloss = str(row.get(self.GLOSS_COLUMN, ""))

            # Clean the text and gloss
            raw_gloss_text = self._clean_text(raw_text)
            cleaned_gloss = self._clean_text(raw_gloss).replace(',', ' PUNCT ')

            # Split into non-empty lines
            text_lines = [line.strip() for line in raw_gloss_text.split("\n") if line.strip()]
            gloss_lines = [line.strip() for line in cleaned_gloss.split("\n") if line.strip()]

            # Ensure line count matches
            if len(text_lines) != len(gloss_lines):
                msg.warn(
                    f"Skipped row due to line count mismatch: {len(text_lines)} texts vs {len(gloss_lines)} glosses"
                )
                self.logger.warning(
                    f"Skipped row: {len(text_lines)} texts vs {len(gloss_lines)} glosses"
                )
                continue

            # Process each line pair
            for text_line, gloss_line in zip(text_lines, gloss_lines):
                feats = self._map_gloss(gloss_line)
                tokens = text_line.split()

                # Ensure token count matches feature count
                if len(tokens) != len(feats):
                    msg.warn(
                        f"Token mismatch for text: '{text_line}' (tokens={len(tokens)}, feats={len(feats)})"
                    )
                    self.logger.warning(
                        f"Token mismatch: '{text_line}' (tokens={len(tokens)}, feats={len(feats)})"
                    )
                    continue

                # Append a row with all required columns
                rows.append({
                    'raw_text': raw_text,
                    'translation': raw_translation,
                    'clean_text': raw_gloss_text,
                    'tokens': tokens,
                    'gloss': gloss_line,
                    'UDfeats': feats
                })

        # Construct DataFrame (will be empty if no valid rows)
        columns = ['raw_text', 'translation', 'clean_text', 'tokens', 'gloss', 'UDfeats']
        new_df = pd.DataFrame(rows, columns=columns)
        new_df = new_df[~new_df.apply(self._is_placeholder, axis=1)].reset_index(drop=True)
        return new_df
    
    @staticmethod
    def _is_placeholder(row):
        return (
            row['raw_text'] == 'nan' and
            row['translation'] == 'nan' and
            row['clean_text'] == 'nan' and
            row['tokens'] == ['nan'] and
            row['gloss'] == 'nan' and
            row['UDfeats'] == ['_']
        )


    def _clean_text(self, text: Union[str, float]) -> str:
        """
        Clean and normalize text fields:
        - Collapse ellipses, replace commas, strip punctuation and digits,
            remove bracketed content, and normalize whitespace.
        """
        if not isinstance(text, str):
            return ""

        # Replace double dots, standardize commas, remove outer dots
        text = text.replace('..', '.')
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