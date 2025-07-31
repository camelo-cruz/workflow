import os
import re
import torch
import warnings
import pandas as pd
from tqdm import tqdm
import logging

from abc import ABC
from inference.pii_identifier.factory import PIIIdentifierFactory
from inference.transcription.factory import TranscriptionStrategyFactory
from utils.functions import (
    set_global_variables,
    clean_german_transcription,
    find_ffmpeg,
    format_excel_output,
)
from inference.processors.abstract import DataProcessor  # adjust import path as needed

# Global setup
LANGUAGES, NO_LATIN, OBLIGATORY_COLUMNS = set_global_variables()
warnings.filterwarnings("ignore")
ffmpeg_path = find_ffmpeg()


class TranscriptionProcessor(DataProcessor):
    """
    Processes directories of audio files, transcribing them into a trials-and-sessions sheet.
    """

    def __init__(self, language: str, instruction: str, device: str | None = None):
        super().__init__(language, instruction)
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.pii_identifier = PIIIdentifierFactory.get_strategy(self.language)
        self.strategy = TranscriptionStrategyFactory.get_strategy(self.language)
        print('initialized transcription strategy:', self.strategy.__class__.__name__)
        self.filename_regexp = re.compile(
            r'blockNr_(?P<block>\d+)_taskNr_(?P<task>\d+)_trialNr_(?P<trial>\d+).*'
        )

    def _find_files(self, base_dir: str) -> list[str]:
        # find parent dirs containing a 'binaries' subfolder
        bases = set()
        for subdir, _, files in os.walk(base_dir):
            if 'binaries' in os.path.basename(subdir):
                bases.add(os.path.abspath(os.path.join(subdir, '..')))
        return sorted(bases)

    def _read_file(self, base_dir: str) -> pd.DataFrame:
        # load trials-and-sessions sheet
        df, out_file = self.load_trials_data(base_dir)
        self._current_out_file = out_file
        self._current_base_dir = base_dir
        return df

    def _process_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        # iterate over audio files in 'binaries' and append transcriptions
        bin_dir = os.path.join(self._current_base_dir, 'binaries')
        files = sorted(os.listdir(bin_dir))
        count = 0
        for file in tqdm(files, desc="Transcribing audio"):
            if not file.lower().endswith(('.mp3', '.mp4', '.m4a')):
                continue
            count += 1
            path = os.path.join(bin_dir, file)
            try:
                text = self.strategy.transcribe(path)
                if self.pii_identifier:
                    _, text = self.pii_identifier.identify_and_annotate(text)
                if self.language == 'de':
                    text = clean_german_transcription(text)
                self.add_transcription_to_df(
                    df,
                    file,
                    text,
                    count,
                    self.filename_regexp,
                )
            except Exception as e:
                self.logger.info(f"Error processing file '{file}': {e}")
        return df

    def _write_file(self, _: str, df: pd.DataFrame):
        # write out annotated sheet and apply formatting
        df.to_excel(self._current_out_file, index=False)
        highlight_col = (
            'transcription_original_script'
            if self.language in NO_LATIN
            else 'latin_transcription_everything'
        )
        format_excel_output(self._current_out_file, highlight_col)

    def load_trials_data(self, base_dir: str):
        csv_file = os.path.join(base_dir, 'trials_and_sessions.csv')
        excel_file = os.path.join(base_dir, 'trials_and_sessions.xlsx')
        excel_out = os.path.join(base_dir, 'trials_and_sessions_annotated.xlsx')

        if os.path.exists(csv_file):
            df = pd.read_csv(csv_file, encoding='utf-8')
        elif os.path.exists(excel_file):
            df = pd.read_excel(excel_file, encoding='utf-8')
        else:
            raise FileNotFoundError(
                "No trials_and_sessions file found in the directory."
            )

        for col in OBLIGATORY_COLUMNS:
            df[col] = df.get(col, "")

        if self.language not in NO_LATIN:
            df["transcription_original_script"] = ""
            df["transcription_original_script_utterance_used"] = ""

        return df, excel_out

    def _append_to_cell(self, df, idx, column, text):
        old = df.at[idx, column]
        df.at[idx, column] = ("" if pd.isna(old) else old) + text

    def add_transcription_to_df(
        self, df, file, transcription, count, filename_regexp
    ):
        series = df[df.isin([file])].stack()
        text_auto = f"{count}: {transcription}"
        suffix = " - " if series.empty else " "
        col_name = (
            'transcription_original_script'
            if self.language in NO_LATIN
            else 'latin_transcription_everything'
        )

        if series.empty:
            match = filename_regexp.search(file)
            if not match:
                self.logger.info(
                    f"File '{file}' does not match block/task/trial pattern. Skipping."
                )
                return
            blk = int(match['block'])
            tsk = int(match['task'])
            trl = int(match['trial'])
            cond = (
                (df['Block_Nr'] == blk)
                & (df['Task_Nr'] == tsk)
                & (df['Trial_Nr'] == trl)
            )
            if df.loc[cond].empty:
                self.logger.info(
                    f"No row for block {blk}, task {tsk}, trial {trl}. Skipping '{file}'."
                )
                return
            miss_col = next(
                f"missing_filename_{i}"
                for i in range(1, 10)
                if f"missing_filename_{i}" not in df.columns
                or df.loc[cond, f"missing_filename_{i}"].isna().all()
            )
            df.loc[cond, miss_col] = file
            for idx in df.loc[cond].index:
                self._append_to_cell(df, idx, 'automatic_transcription', text_auto + suffix)
                self._append_to_cell(df, idx, col_name,      text_auto + suffix)
        else:
            for (row_idx, _), _ in series.items():
                self._append_to_cell(df, row_idx, 'automatic_transcription', text_auto + suffix)
                self._append_to_cell(df, row_idx, col_name,      text_auto + suffix)
    
    def process(self, input_dir: str):
        files = self._find_files(input_dir)
        for path in tqdm(files, desc=f"Processing {self.__class__.__name__} files"):
            log_name = f"{self.__class__.__name__}.log"
            log_path = os.path.join(path, log_name)
            print(f"[DEBUG] Writing log to: {log_path}")

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
