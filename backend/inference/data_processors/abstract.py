from abc import ABC, abstractmethod
import os
import re
import pandas as pd
from tqdm import tqdm

class AbstractSessionProcessor(ABC):
    """
    Common base for processing directories of session-based transcripts/
    glosses/etc. Implements directory walking and Excel I/O.
    """
    FILENAME_PATTERN = re.compile(
        r'blockNr_(?P<block>\d+)_taskNr_(?P<task>\d+)_trialNr_(?P<trial>\d+)')

    def __init__(self, input_dir: str, language: str, verbose: bool = True):
        self.input_dir = input_dir
        self.language = language
        self.verbose = verbose

    def process_sessions(self):
        """
        Walk each 'binaries' subfolder, load its DataFrame, and apply processing.
        """
        for subdir, _, files in os.walk(self.input_dir):
            if 'binaries' not in subdir:
                continue

            base_dir = os.path.abspath(os.path.join(subdir, '..'))
            df, excel_path = self._load_session_dataframe(base_dir)
            if df is None:
                continue

            self._before_session(base_dir, df)
            count = 0
            files = sorted(f for f in files if f.lower().endswith(self.file_extensions()))

            for filename in tqdm(files, desc=f"{self.__class__.__name__} in {base_dir}"):
                count += 1
                filepath = os.path.join(subdir, filename)
                if self.verbose:
                    tqdm.write(f"Processing {filename} ({count}/{len(files)})")
                try:
                    self._process_file(df, filename, filepath, count)
                except Exception as e:
                    self._on_error(filename, e)

            self._after_session(base_dir, df, excel_path)

    def _load_session_dataframe(self, base_dir: str):
        """Load or create the trial/session DataFrame for this session."""
        try:
            df, out_file = self._get_input_output_paths(base_dir)
            # ensure obligatory columns, Latin vs non-Latin, etc.
            df = self.prepare_dataframe(df)
            return df, out_file
        except FileNotFoundError as e:
            self._on_missing_trials(e)
            return None, None

    @abstractmethod
    def _get_input_output_paths(self, base_dir: str):
        """Return (df, output_path) for a given session directory."""
        pass

    @abstractmethod
    def prepare_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Initialize columns and metadata on raw DataFrame."""
        pass

    @abstractmethod
    def file_extensions(self) -> tuple[str, ...]:
        """Return tuple of file extensions to process (e.g. ('.mp3','.wav'))."""
        pass

    @abstractmethod
    def _process_file(self, df: pd.DataFrame, filename: str, path: str, index: int):
        """Process a single file: transcribe, gloss, annotate, etc."""
        pass

    def _before_session(self, base_dir: str, df: pd.DataFrame):
        """Hook before starting file-level processing."""
        pass

    def _after_session(self, base_dir: str, df: pd.DataFrame, output_path: str):
        """Save, format, and cleanup after all files in a session."""
        df.to_excel(output_path, index=False)
        self._format_excel(output_path)

    @abstractmethod
    def _format_excel(self, excel_path: str):
        """Run post-save formatting (column widths, styles)."""
        pass

    def _on_missing_trials(self, exception: Exception):
        # log or warn
        print(f"Skipping session: {exception}")

    def _on_error(self, filename: str, exception: Exception):
        # log error
        print(f"Error processing {filename}: {exception}")
