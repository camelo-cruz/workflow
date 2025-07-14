import os
import re
import sys
import logging
from pathlib import Path
from abc import ABC, abstractmethod
from typing import List, Union

import pandas as pd
from tqdm import tqdm

from utils.functions import (
    find_language,
    set_global_variables,
)

class BasePreprocessor(ABC):
    """
    Abstract base class for data preprocessing:
      - Discovers input files, reads data, applies cleaning, and writes a combined output.
      - Processes all files into a single DataFrame and writes one CSV.
    """
    # Default column names
    TEXT_COLUMN = "latin_transcription_utterance_used"
    GLOSS_COLUMN = "glossing_utterance_used"
    TRANSLATION_COLUMN = "translation_utterance_used"

    def __init__(self, lang: str, study: str, file_pattern: str = "*annotated.xlsx") -> None:
        self.study = study
        self.file_pattern = file_pattern

        # Language setup
        self.LANGUAGES, self.NO_LATIN, self.OBLIGATORY_COLUMNS = set_global_variables()
        self.lang = find_language(lang, self.LANGUAGES)

        # Ensure UTF-8 for stdout/stderr once
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

        # Logger configuration
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
        self.logger.addHandler(handler)

    def preprocess(self, input_dir: Union[str, Path]) -> None:
        """
        Main entry point: finds matching files, processes each,
        aggregates into one DataFrame, and writes a single CSV.
        Accepts a path string or Path; converts internally.
        """
        input_dir = Path(input_dir)
        files = self._find_files(input_dir)
        log_path = input_dir / f"{self.__class__.__name__}.log"

        # File handler for detailed logs
        file_handler = logging.FileHandler(log_path, mode="a", encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
        self.logger.addHandler(file_handler)

        processed_dfs: List[pd.DataFrame] = []

        try:
            for path in tqdm(files, desc=f"Processing {input_dir}"):
                self.logger.info(f"Starting session: {path.name}")
                try:
                    df = self._read_file(path)
                    self.logger.info(f"Loaded DataFrame ({len(df)} rows) from {path.name}")

                    processed = self._process_dataframe(df)
                    processed_dfs.append(processed)
                except Exception as e:
                    self.logger.error(f"Error processing {path.name}: {e}", exc_info=True)

            # Combine all processed data
            if processed_dfs:
                combined = pd.concat(processed_dfs, ignore_index=True)
                self._write_combined_file(combined)
                self.logger.info(f"Wrote combined processed data ({len(combined)} rows)")
            else:
                self.logger.warning("No processed data to write.")
        finally:
            self.logger.removeHandler(file_handler)
            file_handler.close()

    def _find_files(self, base_dir: Path) -> List[Path]:
        matches = list(base_dir.rglob(self.file_pattern))
        self.logger.info(f"Found {len(matches)} files matching '{self.file_pattern}' in {base_dir}")
        return matches

    def _read_file(self, path: Path) -> pd.DataFrame:
        """
        Read data from an Excel file into a DataFrame.
        """
        if path.suffix.lower() == ".xlsx":
            return pd.read_excel(path)
        else:
            raise ValueError(f"Unsupported file format: {path.suffix}")

    def _write_combined_file(self, df: pd.DataFrame) -> None:
        """
        Write the combined DataFrame back to disk as a single CSV.
        """
        data_dir = Path(__file__).parent.parent / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{self.__class__.__name__}_{self.lang}_{self.study}.csv"
        df.to_csv(data_dir / filename, index=False)

    @abstractmethod
    def _process_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Abstract method to process the DataFrame.
        Must be implemented by subclasses for specific logic.
        """
        raise NotImplementedError("Subclasses must implement _process_dataframe")
