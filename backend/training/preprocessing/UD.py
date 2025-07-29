import re
import pandas as pd
from wasabi import msg
from typing import Union
from training.preprocessing.abstract import BasePreprocessor
from utils.functions import load_glossing_rules


class UDPreprocessor(BasePreprocessor):
    """
    Preprocessor that maps Leipzig gloss codes to UD features.
    """
    PLACEHOLDER = '_'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Load and normalize Leipzig→UD mapping once
        glossary = load_glossing_rules("LEIPZIG_GLOSSARY.json")
        self.LEIPZIG2UD = {
            entry["leipzig"].upper(): (entry["category"], key)
            for key, entry in glossary.items()
        }

    def _process_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        rows = []
        # Reset tracking sets for each run
        self.tokens_without_gloss = set()
        self.unknown_codes = set()

        for idx, row in df.iterrows():
            raw_text = str(row.get(self.TEXT_COLUMN, ""))
            raw_gloss = str(row.get(self.GLOSS_COLUMN, ""))

            raw_gloss_text = self._clean_text(raw_text)
            cleaned_gloss = self._clean_text(raw_gloss)

            text_lines = [line.strip() for line in raw_gloss_text.split("\n") if line.strip()]
            gloss_lines = [line.strip() for line in cleaned_gloss.split("\n") if line.strip()]

            if len(text_lines) != len(gloss_lines):
                msg.warn(f"Skipped row due to line count mismatch: {len(text_lines)} texts vs {len(gloss_lines)} glosses")
                self.logger.warning(
                    f"Skipped row: {len(text_lines)} texts vs {len(gloss_lines)} glosses"
                )
                continue

            for text_line, gloss_line in zip(text_lines, gloss_lines):
                feats = self._map_gloss(gloss_line)
                tokens = text_line.split()

                if len(tokens) != len(feats):
                    msg.warn(
                        f"Token mismatch for text: '{tokens} vs {feats}' "
                        f"(tokens={len(tokens)}, feats={len(feats)})"
                    )
                    self.logger.warning(
                        f"Token mismatch for text: '{tokens} vs {feats}' "
                        f"(tokens={len(tokens)}, feats={len(feats)})"
                    )
                    continue

                rows.append({
                    'raw_text': raw_text,
                    'clean_text': raw_gloss_text,
                    'tokens': tokens,
                    'gloss': gloss_line,
                    'UDfeats': feats
                })

        columns = ['raw_text', 'clean_text', 'tokens', 'gloss', 'UDfeats']
        new_df = pd.DataFrame(rows, columns=columns)
        # Filter out pure placeholder rows
        new_df = new_df[~new_df.apply(self._is_placeholder, axis=1)].reset_index(drop=True)

        # Log any missing or unknown items
        self._after_write()
        return new_df

    @staticmethod
    def _is_placeholder(row):
        return (
            row['raw_text'] == 'nan' and
            row['clean_text'] == 'nan' and
            row['tokens'] == ['nan'] and
            row['gloss'] == 'nan' and
            row['UDfeats'] == [UDPreprocessor.PLACEHOLDER]
        )

    def _clean_text(self, text: Union[str, float]) -> str:
        if not isinstance(text, str):
            return ""
        text = re.sub(r'\.{2,}', '', text)
        text = re.sub(r"[\[\(\{]\d+[\]\)\}]", "", text)
        text = text.replace('(', ' ( ').replace(')', ' ) ')
        text = text.replace(',', '')
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _map_gloss(self, gloss: str) -> list[str]:
        if not isinstance(gloss, str):
            return []
        feats = []
        for token in gloss.split():
            is_gloss = '-' in token or token.isupper()
            if not is_gloss:
                feats.append(self.PLACEHOLDER)
                self.tokens_without_gloss.add(token)
                continue

            parts = [c for c in token.split('-') if c]
            # Drop leading lowercase codes
            if parts and parts[0].islower():
                parts.pop(0)
            mapped = []
            for raw_code in parts:
                code = raw_code
                pair = self.LEIPZIG2UD.get(code)
                if not pair:
                    self.unknown_codes.add(code)
                else:
                    mapped.append(f"{pair[0]}={pair[1]}")

            feats.append('|'.join(mapped) if mapped else self.PLACEHOLDER)
        return feats

    def _after_write(self):
        msg.warn(f"Tokens without glosses: {self.tokens_without_gloss}") if self.tokens_without_gloss else None
        self.logger.warning(f"Tokens without glosses: {self.tokens_without_gloss}")
        msg.warn(f"Unknown codes encountered: {self.unknown_codes}") if self.unknown_codes else None
        self.logger.warning(f"Unknown codes encountered: {self.unknown_codes}")