from abc import ABC, abstractmethod
import os
import logging
from pathlib import Path
import pandas as pd
from tqdm import tqdm

from utils.functions import (
    find_language,
    set_global_variables,
    format_excel_output,
)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(name)s %(levelname)s: %(message)s",
                    datefmt="%H:%M:%S")

LANGUAGES, NO_LATIN, OBLIGATORY_COLUMNS = set_global_variables()

class DataProcessor(ABC):
    def __init__(self, language: str, instruction: str):
        self.language = find_language(language, LANGUAGES)
        self.instruction = instruction
        # one logger per subclass
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
        self.columns_to_highlight = None

    def process(self, input_dir: str):
        files = self._find_files(input_dir)
        for path in tqdm(files, desc=f"Processing {self.__class__.__name__} files"):
            log_name = f"{self.__class__.__name__}.log"
            log_path = os.path.join(input_dir, log_name)

            fh = logging.FileHandler(log_path, mode="a")
            fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
            self.logger.addHandler(fh)

            try:
                self.logger.info(f"Processing Session {path}")
                df = self._read_file(path)
                self.logger.info(f"Loaded DataFrame with {len(df)} rows")
                df = self._process_dataframe(df)
                self._write_file(path, df)
            finally:
                self.logger.removeHandler(fh)
                fh.close()

    def _find_files(self, base_dir: str) -> list[str]:
        matches = []
        for root, _, files in os.walk(base_dir):
            for f in files:
                if f.endswith("annotated.xlsx"):
                    matches.append(os.path.join(root, f))
        # this info will go to whichever handlers are attached at the moment
        self.logger.info(f"Found {len(matches)} files in {base_dir}")
        return matches

    def _read_file(self, path: str) -> pd.DataFrame:
        return pd.read_excel(path)

    def _write_file(self, path: str, df: pd.DataFrame):
        extra_cols = [c for c in df.columns if c not in OBLIGATORY_COLUMNS]
        df = df[extra_cols + [c for c in OBLIGATORY_COLUMNS if c in df.columns]]
        df.to_excel(path, index=False)
        self.logger.info(f"Wrote output to {path}")
        if self.columns_to_highlight:
            format_excel_output(path, self.columns_to_highlight)

    @abstractmethod
    def _process_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        pass
