import os
import time
import logging
import pandas as pd
from tqdm import tqdm
from utils.functions import find_language, setup_logging, format_excel_output, set_global_variables
from .translation.factory import TranslationStrategyFactory


LANGUAGES, NO_LATIN, OBLIGATORY_COLUMNS = set_global_variables()

logger = logging.getLogger(__name__)


class Translator:
    def __init__(
        self,
        input_dir: str,
        language: str,
        instruction: str,
        device: str = "cpu",
    ):
        """
        Initializes the Translator.

        Args:
            input_dir (str): Directory containing annotated Excel files.
            language (str): Language name or code for translation source.
            instruction (str): One of 'automatic_transcription',
                'corrected_transcription', or 'sentences'.
            device (str): Torch device to use ('cpu' or 'cuda').
        """
        self.input_dir = input_dir
        self.language_code = find_language(language, LANGUAGES)
        self.instruction = self._normalize_instruction(instruction)
        self.device = device

        self.strategy = TranslationStrategyFactory.get_strategy(self.language_code)

        logger.info(
            f"Initialized Translator (language={language}, code={self.language_code}, "
            f"instruction={self.instruction}, device={self.device}, "
            f"strategy={self.strategy.__class__.__name__})"
        )

    @staticmethod
    def _normalize_instruction(instruction: str) -> str:
        """
        Maps argparse-style instructions to internal keywords.
        """
        mapping = {
            "automatic_transcription": "automatic",
            "corrected_transcription": "corrected",
            "sentences": "sentences",
        }
        return mapping.get(instruction, instruction)

    def process_data(self, verbose: bool = False) -> None:
        """
        Walks through the input directory, translates rows in each annotated.xlsx file,
        saves the updated file, and highlights the chosen translation column.
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
                        logger.info(f"Skipping row {idx}: empty text in '{source_col}'")
                        continue

                    try:
                        # Delegate translation to the chosen strategy
                        translation = self.strategy.translate(str(text))

                        if not translation:
                            logger.info(f"No translation obtained for row {idx}")
                            continue

                        # Write translation into each target column
                        for target_col in cols_map[self.instruction]:
                            df.at[idx, target_col] = translation

                    except Exception as e:
                        logger.exception(f"Row {idx} translation error: {e}")
                        continue

                # Reorder columns: non‐obligatory first, then obligatory
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
