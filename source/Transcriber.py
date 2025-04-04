#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Copyright (C) 2024  Alejandra Camelo Cruz, Arne Goelz

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
...
Leibniz Institute General Linguistics (ZAS)
"""

import os
import re
import warnings
import logging
import argparse
import pandas as pd
import openpyxl
from openpyxl.styles import Font
from tqdm import tqdm
import whisper
import torch

from functions import set_global_variables, find_language, clean_string, find_ffmpeg

# Set global variables and suppress warnings
LANGUAGES, NO_LATIN, OBLIGATORY_COLUMNS, _ = set_global_variables()
warnings.filterwarnings("ignore")

# Configure global logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARNING)
console_handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(console_handler)

ffmpeg_path = find_ffmpeg()


class Transcriber:
    def __init__(self, input_dir, language, device=None):
        self.input_dir = input_dir
        self.language_code = find_language(language, LANGUAGES)
        self.device = device if device is not None else ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = whisper.load_model("large-v3", device=self.device)

    def setup_logging(self, log_file_path):
        """Set up file logging for a given directory."""
        file_handler = logging.FileHandler(log_file_path)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logger.addHandler(file_handler)
        logger.info(f"Logging to {log_file_path}")
        logger.info(f"Using ffmpeg from {ffmpeg_path}")
        return file_handler

    def load_trials_data(self, base_dir):
        """
        Load the trials and sessions data from CSV or Excel.
        Returns the dataframe and the path for the annotated Excel output.
        """
        csv_file_path = os.path.join(base_dir, 'trials_and_sessions.csv')
        excel_file_path = os.path.join(base_dir, 'trials_and_sessions.xlsx')
        excel_output_file = os.path.join(base_dir, 'trials_and_sessions_annotated.xlsx')

        if os.path.exists(csv_file_path):
            df = pd.read_csv(csv_file_path)
        elif os.path.exists(excel_file_path):
            df = pd.read_excel(excel_file_path)
        else:
            raise FileNotFoundError("No trials_and_sessions file found in the directory.")

        # Ensure obligatory columns exist
        for column in OBLIGATORY_COLUMNS:
            if column not in df:
                df[column] = ""
        if self.language_code not in NO_LATIN:
            df["transcription_original_script"] = ""
            df["transcription_original_script_utterance_used"] = ""
        return df, excel_output_file

    def add_transcription_to_df(self, df, file, transcription, count, filename_regexp):
        """
        Add the transcription text to the dataframe.
        If the file is not found in the dataframe, use the block/task/trial
        pattern to locate the row.
        """
        series = df[df.isin([file])].stack()
        if series.empty:
            filename_match = filename_regexp.search(file)
            if filename_match is None:
                logger.warning(f"File '{file}' does not match the block_task_trial pattern. Transcription not added.")
                return
            block_nr = int(filename_match.group('block'))
            task_nr = int(filename_match.group('task'))
            trial_nr = int(filename_match.group('trial'))
            selection_condition = (
                (df['Block_Nr'] == block_nr) &
                (df['Task_Nr'] == task_nr) &
                (df['Trial_Nr'] == trial_nr)
            )
            if df.loc[selection_condition].empty:
                logger.warning(f"No row for block {block_nr}, task {task_nr}, trial {trial_nr}. Transcription not added for '{file}'.")
                return

            # Find the first available missing_filename column
            column_counter = 1
            missing_filename_column = f'missing_filename_{column_counter}'
            while missing_filename_column in df.columns and not df.loc[selection_condition, missing_filename_column].isna().all():
                column_counter += 1
                missing_filename_column = f'missing_filename_{column_counter}'
            df.loc[selection_condition, missing_filename_column] = file

            # Append transcription with a separator
            df.loc[selection_condition, 'automatic_transcription'] = (
                (df.loc[selection_condition, 'automatic_transcription'] or "") + f"{count}: {transcription} - "
            )
            col_name = 'transcription_original_script' if self.language_code in NO_LATIN else 'latin_transcription_everything'
            df.loc[selection_condition, col_name] = (
                (df.loc[selection_condition, col_name] or "") + f"{count}: {transcription} - "
            )
            logger.info(f"File '{file}' added to row for block {block_nr}, task {task_nr}, trial {trial_nr}.")
        else:
            for idx, _ in series.items():
                if pd.isna(df.at[idx[0], "automatic_transcription"]):
                    df.at[idx[0], "automatic_transcription"] = ""
                df.at[idx[0], "automatic_transcription"] += f"{count}: {transcription} "
                col_name = 'transcription_original_script' if self.language_code in NO_LATIN else 'latin_transcription_everything'
                if pd.isna(df.at[idx[0], col_name]):
                    df.at[idx[0], col_name] = ""
                df.at[idx[0], col_name] += f"{count}: {transcription} "

    def format_excel_output(self, excel_output_file):
        """Apply red font formatting to target columns in the Excel output."""
        wb = openpyxl.load_workbook(excel_output_file)
        ws = wb.active
        red_font = Font(color="FF0000")
        target_columns = ['transcription_original_script', 'latin_transcription_everything']

        # Map target columns to their column index from header row
        header_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True))
        column_indexes = {col_name: idx + 1 for idx, col_name in enumerate(header_row) if col_name in target_columns}

        # Apply red font for each cell in the target columns
        for row in ws.iter_rows(min_row=2):
            for col_name, col_idx in column_indexes.items():
                cell = row[col_idx - 1]
                if cell.value:
                    cell.font = red_font

        wb.save(excel_output_file)
        logger.info(f"Excel formatting applied and saved to '{excel_output_file}'.")

    def process_data(self, verbose=False):
        """Walk through the input directory, process audio files, and update the trials file."""
        filename_regexp = re.compile(
            r'blockNr_(?P<block>\d+)_taskNr_(?P<task>\d+)_trialNr_(?P<trial>\d+).*'
        )
        for subdir, _, files in os.walk(self.input_dir):
            if 'binaries' not in subdir:
                continue

            logger.info(f"Using device {self.model.device}")
            logger.info(f"Processing directory: {subdir}")
            print(f"Processing {subdir}")
            base_dir = os.path.abspath(os.path.join(subdir, '..'))
            log_file_path = os.path.join(base_dir, "transcription.log")
            file_handler = self.setup_logging(log_file_path)

            try:
                df, excel_output_file = self.load_trials_data(base_dir)
            except FileNotFoundError as e:
                logger.error(e)
                logger.removeHandler(file_handler)
                file_handler.close()
                continue

            count = 0
            files.sort()
            for file in tqdm(files, desc="Transcribing"):
                if not file.lower().endswith(('.mp3', '.mp4', '.m4a')):
                    continue
                count += 1
                audio_file_path = os.path.abspath(os.path.join(subdir, file))
                logger.debug(f"Processing file {count}/{len(files)}: {audio_file_path}")
                try:
                    # Handle Chinese differently with an initial prompt
                    if self.language_code == 'zh':
                        result = self.model.transcribe(
                            audio_file_path,
                            language=self.language_code,
                            initial_prompt="请使用简体中文转录。"
                        )
                        transcription = result["text"].replace("请使用简体中文转录。", "").replace("使用简体中文转录。", "")
                    else:
                        result = self.model.transcribe(audio_file_path, language=self.language_code)
                        transcription = result["text"]

                    transcription = clean_string(transcription)
                    if verbose:
                        tqdm.write(transcription)
                    self.add_transcription_to_df(df, file, transcription, count, filename_regexp)
                except Exception as e:
                    logger.error(f"Error processing file '{file}': {e}")
                    continue

            df.to_excel(excel_output_file, index=False)
            self.format_excel_output(excel_output_file)
            logger.info(f"Transcription and annotation completed for '{subdir}'.")
            logger.removeHandler(file_handler)
            file_handler.close()


def main():
    parser = argparse.ArgumentParser(description="Automatic transcription")
    parser.add_argument("input_dir", help="Directory containing audio files")
    parser.add_argument("language", help="Language of the audio content")
    parser.add_argument("--verbose", action="store_true", help="Print detailed output")
    args = parser.parse_args()

    transcriber = Transcriber(args.input_dir, args.language)
    transcriber.process_data(verbose=args.verbose)


if __name__ == "__main__":
    main()