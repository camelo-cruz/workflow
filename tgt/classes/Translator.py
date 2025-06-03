import os
import sys
import time
import logging
import argparse

import pandas as pd
import torch
import openpyxl
from openpyxl.styles import Font
from tqdm import tqdm
from dotenv import load_dotenv
from deep_translator import GoogleTranslator
import deepl
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
        self.language_code = find_language(language, LANGUAGES)
        self.instruction = self._normalize_instruction(instruction)
        self.device = device

        self.model = None
        self.tokenizer = None

        if self.instruction == "automatic":
            self._load_pretrained_model()

        logger.info(
            f"Initialized Translator for language: {language} "
            f"(code: {self.language_code}), instruction: {self.instruction}, device: {self.device}"
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

    def _load_pretrained_model(self) -> None:
        """
        Loads the Facebook NLLB-200 model and tokenizer for automatic translation.
        """
        try:
            self.model = AutoModelForSeq2SeqLM.from_pretrained(
                "facebook/nllb-200-1.3B"
            ).to(self.device)
            self.tokenizer = AutoTokenizer.from_pretrained(
                "facebook/nllb-200-1.3B", src_lang=f"{self.language_code}_Latn"
            )
            logger.info("Loaded NLLB-200 model and tokenizer")
        except Exception as e:
            logger.exception(f"Failed to load pretrained model: {e}")
            raise

    def translate_with_pretrained(self, text: str) -> str:
        """
        Uses the NLLB-200 model to translate a single string to English.

        Args:
            text (str): Text in source language.

        Returns:
            str: Translated text in English.
        """
        start = time.time()
        inputs = self.tokenizer(text, return_tensors="pt").to(self.device)
        translated_tokens = self.model.generate(
            **inputs,
            forced_bos_token_id=self.tokenizer.convert_tokens_to_ids("eng_Latn"),
        )
        translated = self.tokenizer.batch_decode(
            translated_tokens, skip_special_tokens=True
        )[0]
        logger.info(f"Translated with NLLB-200 in {time.time() - start:.2f}s")
        return translated

    def translate_with_deepl(self, text: str) -> str | None:
        """
        Uses DeepL API to translate a string to English, falling back if source is undetected.

        Args:
            text (str): Text in source language.

        Returns:
            str | None: Translated text or None on failure.
        """
        try:
            base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
            secrets_path = os.path.join(base_path, "materials", "secrets.env")
            if not os.path.exists(secrets_path):
                logger.error(f"Secrets file not found: {secrets_path}")
                sys.exit(1)

            load_dotenv(secrets_path, override=True)
            api_key = os.getenv("API_KEY")
            if not api_key:
                raise ValueError("API_KEY not found in environment")

            client = deepl.DeepLClient(api_key)
            code = self.language_code.upper()
            if code.lower() == "pt":
                code = "PT-BR"

            try:
                result = client.translate_text(text, source_lang=code, target_lang="EN-US")
            except deepl.DeepLException:
                result = client.translate_text(text, target_lang="EN-US")

            return result.text
        except Exception as e:
            logger.exception(f"DeepL translation failed: {e}")
            return None

    def process_data(self, verbose: bool = False) -> None:
        """
        Walks through the input directory, translates rows in each annotated.xlsx file,
        saves the updated file, and highlights the chosen translation column.

        Args:
            verbose (bool): If True, prints additional debug info.
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
                    else:  # 'sentences'
                        source_col = sent_col

                    text = row.get(source_col)
                    if pd.isna(text) or not str(text).strip():
                        logger.info(f"Skipping row {idx}: empty text in '{source_col}'")
                        continue

                    try:
                        # Perform translation based on instruction
                        if self.instruction in ("sentences", "corrected"):
                            trans = GoogleTranslator(
                                source=self.language_code, target="en"
                            ).translate(text=str(text))
                        else:  # 'automatic'
                            trans = self.translate_with_pretrained(str(text))

                        if not trans:
                            logger.info(f"No translation obtained for row {idx}")
                            continue

                        # Write translation into each target column
                        for target_col in cols_map[self.instruction]:
                            df.at[idx, target_col] = trans

                    except Exception as e:
                        logger.exception(f"Row {idx} translation error: {e}")
                        continue

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

        logger.info(f"Completed translation in {time.time() - start_time:.2f}s")