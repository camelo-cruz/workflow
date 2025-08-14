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
        glossary = load_glossing_rules("LEIPZIG_GLOSSARY.json")
        self.LEIPZIG2UD = {
            entry["leipzig"].upper(): (entry["category"], key)
            for key, entry in glossary.items()
        }
        self._rows_error = False

    # --- helpers ---
    @staticmethod
    def _to_str(x) -> str:
        return "" if pd.isna(x) else str(x)

    @staticmethod
    def _normalize_newlines(s: str) -> str:
        # make real line breaks and standardize
        return s.replace("\r\n", "\n").replace("\r", "\n").replace("\\n", "\n")

    def _clean_line(self, text: Union[str, float]) -> str:
        """Clean within a single line (no newline collapsing)."""
        if not isinstance(text, str):
            return ""
        text = re.sub(r'\.{2,}', '', text)                         # drop runs of dots
        text = re.sub(r"[\[\(\{]\d+[\]\)\}]", "", text)            # remove [12] (etc.)
        text = re.sub(r"[\[\(\{\]\)\}]", "", text)                 # stray brackets
        text = re.sub(r"[ \t]+", " ", text).strip()                # normalize spaces/tabs
        return text

    # --- core ---
    def _process_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        rows = []
        self.tokens_without_gloss = set()
        self.unknown_codes = set()

        for idx, row in df.iterrows():
            raw_text  = self._normalize_newlines(self._to_str(row.get(self.TEXT_COLUMN, "")))
            raw_gloss = self._normalize_newlines(self._to_str(row.get(self.GLOSS_COLUMN, "")))

            # split into lines after normalization
            text_lines_raw  = [l for l in raw_text.split("\n")  if l.strip()]
            gloss_lines_raw = [l for l in raw_gloss.split("\n") if l.strip()]

            text_lines  = [self._clean_line(l) for l in text_lines_raw]
            gloss_lines = [self._clean_line(l) for l in gloss_lines_raw]

            if len(text_lines) != len(gloss_lines):
                msg.warn(f"Skipped row {idx}: {len(text_lines)} texts vs {len(gloss_lines)} glosses")
                self.logger.warning(f"Skipped row {idx}: {len(text_lines)} texts vs {len(gloss_lines)} glosses")
                continue

            for text_line, gloss_line in zip(text_lines, gloss_lines):
                feats = self._map_gloss(gloss_line)
                tokens = text_line.split()

                if len(tokens) != len(feats):
                    msg.warn(
                        f"Token mismatch (row {idx}): tokens={len(tokens)} vs feats={len(feats)} "
                        f"-> {tokens} vs {feats}"
                    )
                    self.logger.warning(
                        f"Token mismatch (row {idx}): tokens={len(tokens)} vs feats={len(feats)} "
                        f"-> {tokens} vs {feats}"
                    )
                    continue

                rows.append({
                    'raw_text': raw_text,
                    'clean_text': "\n".join(text_lines),   # preserve line breaks
                    'tokens': tokens,
                    'gloss': gloss_line,
                    'UDfeats': feats
                })

        columns = ['raw_text', 'clean_text', 'tokens', 'gloss', 'UDfeats']
        new_df = pd.DataFrame(rows, columns=columns)

        # Filter out pure placeholder rows
        if not new_df.empty:
            new_df = new_df[~new_df.apply(self._is_placeholder, axis=1)].reset_index(drop=True)
        return new_df

    @staticmethod
    def _is_placeholder(row):
        # Treat NaN as empty; be robust to missing keys
        raw_text  = row.get('raw_text', "")
        clean_txt = row.get('clean_text', "")
        tokens    = row.get('tokens', [])
        gloss     = row.get('gloss', "")
        feats     = row.get('UDfeats', [])

        raw_text  = "" if pd.isna(raw_text)  else raw_text
        clean_txt = "" if pd.isna(clean_txt) else clean_txt
        gloss     = "" if pd.isna(gloss)     else gloss

        return (
            raw_text == '' and clean_txt == '' and gloss == '' and
            isinstance(tokens, list) and tokens == ['nan'] and
            isinstance(feats, list) and feats == [UDPreprocessor.PLACEHOLDER]
        )

    def _map_gloss(self, gloss: str) -> list[str]:
        if not isinstance(gloss, str):
            return []
        feats = []
        for token in gloss.split():
            is_gloss = ('-' in token) or token.isupper()
            if not is_gloss:
                feats.append(self.PLACEHOLDER)
                self.tokens_without_gloss.add(token)
                continue

            parts = [c for c in token.split('-') if c]
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
        if self.tokens_without_gloss:
            msg.warn(f"Tokens without glosses: {self.tokens_without_gloss}")
            self.logger.warning(f"Tokens without glosses: {self.tokens_without_gloss}")

        if self.unknown_codes:
            msg.warn(f"Unknown codes encountered: {self.unknown_codes}")
            self.logger.warning(f"Unknown codes encountered: {self.unknown_codes}")
            raise ValueError(
                f"Unknown codes encountered: {self.unknown_codes}. "
                "Please check glossing rules or data."
            )

        if self._rows_error:
            msg.warn(f"Not enough rows  after preprocessing. Please check your data.")
            self.logger.warning("Not enough rows after preprocessing. Please check your data.")
            raise ValueError("Not enough rows after preprocessing. Please check your data.")
