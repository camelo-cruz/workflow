import os
import sys
import time
import logging

import pandas as pd
import torch
import openpyxl
from openpyxl.styles import Font
from tqdm import tqdm

from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

from utils.functions import (
    set_global_variables,
    find_language,
    setup_logging,
    format_excel_output,
)

# Initialize global variables for language settings
LANGUAGES, NO_LATIN, OBLIGATORY_COLUMNS = set_global_variables()
logger = logging.getLogger(__name__)


class Translator:
    def __init__(self, input_dir: str, language: str, instruction: str, device: str = "cpu"):
        """
        Initializes the Translator.

        Args:
            input_dir (str): Directory containing annotated Excel files.
            language (str): Language name or code for translation source.
            instruction (str): One of 'automatic_transcription', 'corrected_transcription', or 'sentences'.
            device (str): Torch device to use ('cpu' or 'cuda').
        """
        self.input_dir = input_dir
        # find_language(...) returns a normalized two-letter code (e.g. 'pt', 'de', 'ru', etc.)
        self.language_code = find_language(language, LANGUAGES)
        self.instruction = self._normalize_instruction(instruction)
        self.device = device

        # MarianMT model/tokenizer (for both language-specific and multilingual fallback)
        self.marian_model = None
        self.marian_tokenizer = None

        # Flag to indicate if we're using the multilingual model
        self.using_multilingual = False

        # Load Marian models (language-specific first; if that fails, load multilingual)
        self._load_marian_model()

        logger.info(
            f"Initialized Translator for language: {language} "
            f"(code: {self.language_code}), instruction: {self.instruction}, device: {self.device}"
            + (", using multilingual fallback" if self.using_multilingual else "")
        )

    @staticmethod
    def _normalize_instruction(instruction: str) -> str:
        """
        Maps argparse-style instructions to internal keywords.

        Args:
            instruction (str): One of the argparse choices.

        Returns:
            str: Normalized instruction key.
        """
        mapping = {
            "automatic_transcription": "automatic",
            "corrected_transcription": "corrected",
            "sentences": "sentences",
        }
        return mapping.get(instruction, instruction)

    def _load_marian_model(self) -> None:
        """
        Attempts to load a MarianMT model:
          1. Try "Helsinki-NLP/opus-mt-<lang>-en"
          2. On failure, fall back to "Helsinki-NLP/opus-mt-mul-en"

        If multilingual falls back, set self.using_multilingual = True.
        """
        # First attempt: language-specific
        lang_model_name = f"Helsinki-NLP/opus-mt-{self.language_code}-en"
        try:
            self.marian_tokenizer = AutoTokenizer.from_pretrained(lang_model_name)
            self.marian_model = (
                AutoModelForSeq2SeqLM.from_pretrained(lang_model_name)
                .to(self.device)
            )
            logger.info(f"Loaded MarianMT model and tokenizer: {lang_model_name}")
            return

        except Exception as e:
            logger.warning(
                f"Could not load MarianMT model '{lang_model_name}': {e}. "
                "Falling back to multilingual model."
            )

        # Fallback: multilingual → English
        multi_model_name = "Helsinki-NLP/opus-mt-mul-en"
        try:
            self.marian_tokenizer = AutoTokenizer.from_pretrained(multi_model_name)
            self.marian_model = (
                AutoModelForSeq2SeqLM.from_pretrained(multi_model_name)
                .to(self.device)
            )
            self.using_multilingual = True
            logger.info(f"Loaded multilingual MarianMT model: {multi_model_name}")
            return

        except Exception as e:
            logger.exception(
                f"Failed to load multilingual MarianMT model '{multi_model_name}': {e}. "
                "No Marian model is available."
            )
            # Leave marian_model/tokenizer as None
            self.marian_model = None
            self.marian_tokenizer = None
            self.using_multilingual = False

    def _get_multilingual_prefix(self) -> str:
        """
        Returns the appropriate three-letter ISO token for the source language,
        e.g. 'por' for Portuguese, 'deu' for German, etc., wrapped as '>>xxx<<'.

        If we don't have a mapping, fallback to an empty prefix (the model will attempt auto-detect,
        but results may be subpar).
        """
        iso_map = {
            "ar": "ara",
            "cs": "ces",
            "de": "deu",
            "en": "eng",
            "es": "spa",
            "fr": "fra",
            "it": "ita",
            "nl": "nld",
            "pt": "por",
            "ru": "rus",
            "sv": "swe",
            "zh": "zho",
            # …add more as needed…
        }
        two_letter = self.language_code.lower()
        three_letter = iso_map.get(two_letter)
        if three_letter:
            return f">>{three_letter}<< "
        else:
            # If we don't know a three-letter code, return empty string
            return ""

    def translate_with_marian(self, text: str) -> str | None:
        """
        Uses the MarianMT model to translate a string to English.

        If using the multilingual model, the input will be prefixed with the language token.
        Returns None if no Marian model is loaded or translation fails.
        """
        if self.marian_model is None or self.marian_tokenizer is None:
            return None

        try:
            if self.using_multilingual:
                # Prefix with language token, e.g. ">>por<< " for Portuguese
                prefix = self._get_multilingual_prefix()
                text_to_tokenize = prefix + text
            else:
                text_to_tokenize = text

            start = time.time()
            inputs = self.marian_tokenizer(
                text_to_tokenize,
                return_tensors="pt",
                padding=True,
                truncation=True
            ).to(self.device)

            translated_tokens = self.marian_model.generate(**inputs)
            translated = self.marian_tokenizer.batch_decode(
                translated_tokens, skip_special_tokens=True
            )[0]
            elapsed = time.time() - start
            logger.info(
                f"Translated with MarianMT ({'multilingual' if self.using_multilingual else 'lang-specific'}) "
                f"in {elapsed:.2f}s"
            )
            return translated

        except Exception as e:
            logger.exception(f"MarianMT translation failed at runtime: {e}")
            return None

    def process_data(self, verbose: bool = False) -> None:
        """
        Walks through the input directory, translates rows in each annotated.xlsx file,
        saves the updated file, and highlights the chosen translation column.
        If MarianMT is unavailable (neither lang-specific nor multilingual), rows will be skipped.
        """
        start_time = time.time()
        logger.info(f"Starting translation for directory: {self.input_dir}")

        # Define source-column names based on instruction
        auto_col = "automatic_transcription"
        corr_col = "latin_transcription_everything"
        sent_col = "latin_transcription_utterance_used"

        # Override for non-Latin scripts
        if self.language_code in NO_LATIN:
            corr_col = "transcription_original_script"
            sent_col = "transcription_original_script_utterance_used"

        # Find all "*annotated.xlsx" files recursively
        files = [
            os.path.join(dp, f)
            for dp, dn, filenames in os.walk(self.input_dir)
            for f in filenames
            if f.endswith("annotated.xlsx")
        ]

        for file_path in tqdm(files, desc="Processing files"):
            log_path = os.path.join(os.path.dirname(file_path), "translation.log")
            handler = setup_logging(logger, log_path)
            try:
                logger.info(f"Processing file: {file_path}")
                df = pd.read_excel(file_path)

                # Map of which target columns to write into for each instruction
                cols_map = {
                    "corrected": [
                        "automatic_translation_corrected_transcription",
                        "translation_everything",
                    ],
                    "automatic": ["automatic_translation_automatic_transcription"],
                    "sentences": [
                        "automatic_translation_utterance_used",
                        "translation_utterance_used",
                    ],
                }

                # Iterate row-wise, up to 100 rows
                for idx, row in df.iterrows():
                    if idx >= 100:
                        logger.info(f"Reached max rows at {idx}")
                        break

                    # Select the appropriate source column
                    if self.instruction == "corrected":
                        source_col = corr_col
                    elif self.instruction == "automatic":
                        source_col = auto_col
                    else:
                        source_col = sent_col

                    text = row.get(source_col)
                    if pd.isna(text) or not str(text).strip():
                        logger.debug(f"Skipping row {idx}: empty text in '{source_col}'")
                        continue

                    # Try MarianMT (language-specific or multilingual)
                    trans = self.translate_with_marian(str(text))

                    if trans is None:
                        # No Marian model available, so we skip
                        logger.warning(f"Skipping row {idx}: no MarianMT model could translate.")
                        continue

                    # Write translation into each target column
                    for target_col in cols_map[self.instruction]:
                        df.at[idx, target_col] = trans

                # Reorder columns: non-obligatory first, then obligatory
                extra_cols = [c for c in df.columns if c not in OBLIGATORY_COLUMNS]
                df = df[extra_cols + [c for c in OBLIGATORY_COLUMNS if c in df.columns]]

                # Save back to the same file (overwrites)
                df.to_excel(file_path, index=False)

                # Determine which column to highlight
                if self.instruction == "automatic":
                    column_to_highlight = "automatic_translation_automatic_transcription"
                elif self.instruction == "corrected":
                    column_to_highlight = "automatic_translation_corrected_transcription"
                elif self.instruction == "sentences":
                    column_to_highlight = "translation_utterance_used"
                else:
                    column_to_highlight = None

                # Apply Excel formatting highlight if column exists
                if column_to_highlight and column_to_highlight in df.columns:
                    format_excel_output(file_path, column_to_highlight)

            finally:
                logger.removeHandler(handler)

        elapsed_total = time.time() - start_time
        logger.info(f"Completed translation in {elapsed_total:.2f}s")
