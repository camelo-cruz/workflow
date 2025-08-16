import re
import unicodedata
import pandas as pd
from wasabi import msg
from typing import Union, List
from training.preprocessing.abstract import BasePreprocessor
from utils.functions import load_glossing_rules

import spacy
from spacy.util import compile_infix_regex, get_lang_class


class UDPreprocessor(BasePreprocessor):
    """
    Preprocessor that maps Leipzig gloss codes to UD features.
    Uses spaCy's BLANK tokenizer (no pretrained weights) for tokenization.
    """
    PLACEHOLDER = '_'

    def __init__(self, *args, preserve_hyphenated: bool = True, **kwargs):
        super().__init__(*args, **kwargs)

        # Build Leipzig->UD map (case-insensitive lookup)
        glossary = load_glossing_rules("LEIPZIG_GLOSSARY.json")
        self.LEIPZIG2UD = {
            entry["leipzig"].upper(): (entry["category"], key)
            for key, entry in glossary.items()
        }

        self.tokens_without_gloss = set()
        self.unknown_codes = set()
        self._rows_error = False

        # ---- spaCy tokenizer (blank lang) ----
        self._nlp = self._build_blank_tokenizer(
            lang=self.lang,
            preserve_hyphenated=preserve_hyphenated
        )

    # ---------- tokenizer ----------
    def _build_blank_tokenizer(self, lang: str, preserve_hyphenated: bool):
        # Try language-specific; fall back to generic 'xx' if that language is not bundled.
        try:
            get_lang_class(lang)  # raises if unsupported
            nlp = spacy.blank(lang)
            msg.info(f"Using spaCy language: {lang}")
            self.logger.info(f"Using spaCy language: {lang}")
        except Exception:
            msg.warn(f"spaCy language '{lang}' not found; using generic 'xx' tokenizer.")
            self.logger.warning(f"spaCy language '{lang}' not found; using generic 'xx' tokenizer.")
            nlp = spacy.blank("xx")

        # Keep hyphenated words (e.g., "T-Shirt") as single tokens, if desired
        if preserve_hyphenated:
            infixes = [x for x in nlp.Defaults.infixes if "-" not in x]
            nlp.tokenizer.infix_finditer = compile_infix_regex(infixes).finditer

        # Keep common number formats as single tokens (e.g., 1.234,56 and 123.45)
        number_re = re.compile(r"""
            ^(
                \d{1,3}(?:\.\d{3})+(?:,\d+)?  |  # 1.234,56
                \d+(?:,\d+)?                  |  # 123,45
                \d+(?:\.\d+)?                    # 123.45
            )$
        """, re.VERBOSE)
        nlp.tokenizer.token_match = number_re.match

        return nlp

    def _tokenize(self, s: str) -> List[str]:
        return [t.text for t in self._nlp.make_doc(s)]

    @staticmethod
    def _is_punct(tok: str) -> bool:
        # True if every char is punctuation (Unicode category P*)
        return tok != "" and all(unicodedata.category(ch).startswith("P") for ch in tok)

    # ---------- helpers ----------
    @staticmethod
    def _to_str(x) -> str:
        return "" if pd.isna(x) else str(x)

    @staticmethod
    def _normalize_newlines(s: str) -> str:
        # standardize line breaks and convert literal "\n" to real newlines
        return s.replace("\r\n", "\n").replace("\r", "\n").replace("\\n", "\n")

    def _clean_line(self, text: Union[str, float]) -> str:
        """Clean within a single line (no newline collapsing)."""
        if not isinstance(text, str):
            return ""
        text = re.sub(r'\.{2,}', '', text)              # drop runs of dots
        text = re.sub(r"[\[\(\{]\d+[\]\)\}]", "", text) # remove [12], (34), {56}
        text = re.sub(r"[\[\(\{\]\)\}]", "", text)      # stray brackets
        text = re.sub(r"[ \t]+", " ", text).strip()     # normalize spaces/tabs
        return text

    # ---------- core ----------
    def _process_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        rows = []
        self.tokens_without_gloss.clear()
        self.unknown_codes.clear()

        for idx, row in df.iterrows():
            raw_text  = self._normalize_newlines(self._to_str(row.get(self.TEXT_COLUMN, "")))
            raw_gloss = self._normalize_newlines(self._to_str(row.get(self.GLOSS_COLUMN, "")))

            # split into lines after normalization
            text_lines  = [self._clean_line(l) for l in raw_text.split("\n")  if l.strip()]
            gloss_lines = [self._clean_line(l) for l in raw_gloss.split("\n") if l.strip()]

            if len(text_lines) != len(gloss_lines):
                msg.warn(f"Skipped row {idx}: {len(text_lines)} texts vs {len(gloss_lines)} glosses")
                self.logger.warning(f"Skipped row {idx}: {len(text_lines)} texts vs {len(gloss_lines)} glosses")
                continue

            # 🔹 Instead of joining lines, emit one row per line
            for text_line, gloss_line in zip(text_lines, gloss_lines):
                tokens = self._tokenize(text_line)
                feats  = self._map_gloss_aligned(tokens, gloss_line)

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
                    'raw_text': text_line,
                    'clean_text': text_line,
                    'tokens': tokens,
                    'gloss': gloss_line,
                    'UDfeats': feats
                })

        columns = ['raw_text', 'clean_text', 'tokens', 'gloss', 'UDfeats']
        new_df = pd.DataFrame(rows, columns=columns)
        if not new_df.empty:
            new_df = new_df[~new_df.apply(self._is_placeholder, axis=1)].reset_index(drop=True)
        return new_df


    @staticmethod
    def _is_placeholder(row):
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

    # ---------- gloss mapping & alignment ----------
    def _map_gloss_aligned(self, text_tokens: List[str], gloss_line: str) -> List[str]:
        """Align gloss tokens to non-punctuation text tokens; punctuation -> '_'."""
        gloss_iter = iter(gloss_line.split())
        feats = []
        for tok in text_tokens:
            if self._is_punct(tok):
                feats.append(self.PLACEHOLDER)  # commas, periods, quotes, etc.
                continue
            gtok = next(gloss_iter, None)
            if gtok is None:
                feats.append(self.PLACEHOLDER)
                continue
            feats.append(self._map_gloss_token(gtok))
        # warn if gloss has leftover tokens (often extra gloss item)
        leftover = next(gloss_iter, None)
        if leftover is not None:
            self.logger.warning(f"Leftover gloss tokens after alignment (e.g., '{leftover}')")
        return feats

    def _map_gloss_token(self, token: str) -> str:
        """Map a single gloss token like PRO-M-3-SG-NOM into UD features."""
        is_gloss = ('-' in token) or token.isupper()
        if not is_gloss:
            self.tokens_without_gloss.add(token)
            return self.PLACEHOLDER
        parts = [c for c in token.split('-') if c]
        if parts and parts[0].islower():
            parts.pop(0)
        mapped = []
        for raw_code in parts:
            code = raw_code.upper()
            pair = self.LEIPZIG2UD.get(code)
            if not pair:
                self.unknown_codes.add(code)
            else:
                mapped.append(f"{pair[0]}={pair[1]}")
        return '|'.join(mapped) if mapped else self.PLACEHOLDER

    # ---------- post-write ----------
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
            msg.warn("Not enough rows after preprocessing. Please check your data.")
            self.logger.warning("Not enough rows after preprocessing. Please check your data.")
            raise ValueError("Not enough rows after preprocessing. Please check your data.")
