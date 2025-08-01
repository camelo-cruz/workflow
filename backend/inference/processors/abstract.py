from abc import ABC, abstractmethod
import os
import logging
import sys
from pathlib import Path
import pandas as pd
from utils.functions import set_global_variables, format_excel_output

# global constants
LANGUAGES, NO_LATIN, OBLIGATORY_COLUMNS = set_global_variables()


class StreamToLogger:
    """File-like object that redirects writes to a logger."""
    def __init__(self, logger: logging.Logger, level: int = logging.INFO):
        self.logger = logger
        self.level = level

    def write(self, message):
        message = message.rstrip()
        if not message:
            return
        for line in message.splitlines():
            self.logger.log(self.level, line)

    def flush(self):
        pass  # logger handles flushing


class Tee:
    """Tee-like object: writes to multiple file-like streams."""
    def __init__(self, *streams):
        self.streams = streams

    def write(self, msg):
        for s in self.streams:
            try:
                s.write(msg)
            except Exception:
                pass

    def flush(self):
        for s in self.streams:
            try:
                s.flush()
            except Exception:
                pass


class DataProcessor(ABC):
    '''
    Finds files to process and writes output. All output (including prints,
    warnings, and progress) is duplicated to both console and a per-session log file.
    '''
    def __init__(self, language: str, instruction: str):
        self.language = language
        self.instruction = instruction
        self.columns_to_highlight = None

        # base logger; per-session handlers will be attached in _attach_session_handler
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False  # avoid bubbling to root

        # capture warnings into logging
        logging.captureWarnings(True)
        warnings_logger = logging.getLogger("py.warnings")
        warnings_logger.setLevel(logging.INFO)
        # let warnings propagate so they go through our logger's handlers
        warnings_logger.propagate = True

        # keep references to original stdout/stderr
        self._orig_stdout = sys.stdout
        self._orig_stderr = sys.stderr

    def _attach_session_handler(self, session_path: str):
        log_name = f"{self.__class__.__name__}.log"
        log_path = os.path.join(Path(session_path).parent, log_name)

        # Clear existing handlers to avoid duplicates
        if self.logger.hasHandlers():
            self.logger.handlers.clear()

        formatter = logging.Formatter("%(asctime)s %(levelname)s: %(message)s")

        # File handler (session log)
        fh = logging.FileHandler(log_path, mode="a", encoding="utf-8")
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

        # Console handler
        ch = logging.StreamHandler(self._orig_stdout)
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)

        # Redirect stdout/stderr so that print() and any library writing to them
        # goes both to console (original) and to logger.
        sys.stdout = Tee(self._orig_stdout, StreamToLogger(self.logger, logging.INFO))
        sys.stderr = Tee(self._orig_stderr, StreamToLogger(self.logger, logging.ERROR))

        self.logger.info(f"Started processing session at {session_path}")
        return fh

    def _detach_session_handler(self, fh):
        # restore stdout/stderr
        sys.stdout = self._orig_stdout
        sys.stderr = self._orig_stderr

        self.logger.info("Detaching session handler")
        self.logger.removeHandler(fh)
        fh.close()

    def process(self, input_dir: str):
        files = self._find_files(input_dir)
        for path in files:
            fh = self._attach_session_handler(path)
            try:
                self.logger.info(f"Processing session {path}")
                df = self._read_file(path)
                self.logger.info(f"Loaded DataFrame with {len(df)} rows")
                df = self._process_dataframe(df)
                self._write_file(path, df)
            finally:
                self.logger.info(f"Finished session {path}")
                self._detach_session_handler(fh)

    def _find_files(self, base_dir: str) -> list[str]:
        matches = []
        for root, _, files in os.walk(base_dir):
            for f in files:
                if f.endswith("annotated.xlsx"):
                    matches.append(os.path.join(root, f))
        self.logger.info(f"Found {len(matches)} matching files in {base_dir}")
        return sorted(matches)

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
