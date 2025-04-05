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
import tempfile
import shutil
import pandas as pd
import openpyxl
from openpyxl.styles import Font
from tqdm import tqdm
import whisper
import torch

from OneDriveHelper import (
    list_online_files,
    download_file_to_temp,
    upload_file_to_onedrive,
    recursive_list_files
)

from functions import (
    set_global_variables, 
    find_language, 
    clean_string, 
    find_ffmpeg
)

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
    def __init__(self, input_dir, language, device=None, drive_id=None, onedrive_token=None):
        """
        input_dir: if local, a valid directory path; if online, a OneDrive folder ID.
        drive_id: if processing online, the drive ID of the selected folder.
        onedrive_token: OneDrive access token (required for online processing).
        """
        self.input_dir = input_dir
        self.language_code = find_language(language, LANGUAGES)
        self.device = device if device is not None else ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = whisper.load_model("large-v3", device=self.device)
        self.drive_id = drive_id
        self.onedrive_token = onedrive_token

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
        Returns the dataframe and the output file path.
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

            column_counter = 1
            missing_filename_column = f'missing_filename_{column_counter}'
            while missing_filename_column in df.columns and not df.loc[selection_condition, missing_filename_column].isna().all():
                column_counter += 1
                missing_filename_column = f'missing_filename_{column_counter}'
            df.loc[selection_condition, missing_filename_column] = file

            df.loc[selection_condition, 'automatic_transcription'] = (
                df.loc[selection_condition, 'automatic_transcription'].fillna("").astype(str) + f"{count}: {transcription} - "
            )

            col_name = 'transcription_original_script' if self.language_code in NO_LATIN else 'latin_transcription_everything'
            df.loc[selection_condition, col_name] = (
                df.loc[selection_condition, col_name].fillna("").astype(str) + f"{count}: {transcription} - "
            )
            logger.info(f"File '{file}' added to row for block {block_nr}, task {task_nr}, trial {trial_nr}.")
        else:
            for idx, _ in series.items():
                if pd.isna(df.at[idx[0], "automatic_transcription"]):
                    df.at[idx[0], "automatic_transcription"] = ""
                df.at[idx[0], "automatic_transcription"] += f"{count}: {transcription}\n"
                col_name = 'transcription_original_script' if self.language_code in NO_LATIN else 'latin_transcription_everything'
                if pd.isna(df.at[idx[0], col_name]):
                    df.at[idx[0], col_name] = ""
                df.at[idx[0], col_name] += f"{count}: {transcription}\n"

    def format_excel_output(self, excel_output_file):
        """Apply red font formatting to target columns in the Excel output."""
        wb = openpyxl.load_workbook(excel_output_file)
        ws = wb.active
        red_font = Font(color="FF0000")
        target_columns = ['transcription_original_script', 'latin_transcription_everything']

        header_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True))
        column_indexes = {col_name: idx + 1 for idx, col_name in enumerate(header_row) if col_name in target_columns}

        for row in ws.iter_rows(min_row=2):
            for col_name, col_idx in column_indexes.items():
                cell = row[col_idx - 1]
                if cell.value:
                    cell.font = red_font

        wb.save(excel_output_file)
        logger.info(f"Excel formatting applied and saved to '{excel_output_file}'.")
    

    def process_data(self, verbose=False):
        """
        Process audio files and update the trials file.
        If self.input_dir exists locally, process using os.walk.
        Otherwise, treat self.input_dir as a OneDrive folder ID and process online.
        """
        filename_regexp = re.compile(
            r'blockNr_(?P<block>\d+)_taskNr_(?P<task>\d+)_trialNr_(?P<trial>\d+).*'
        )
        if os.path.exists(self.input_dir):
            # LOCAL PROCESSING (unchanged)
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
        else:
            # ONLINE PROCESSING: self.input_dir is a OneDrive folder ID.
            if self.onedrive_token is None or self.drive_id is None:
                raise Exception("No OneDrive token or drive ID provided for online processing.")
            online_files = list_online_files(self.onedrive_token, self.drive_id, self.input_dir)
            print("Online files:", [f.get("name") for f in online_files])
            # Identify the trials file (CSV or Excel)
            trials_file = None
            for f in online_files:
                name = f.get("name", "").lower()
                if "trials_and_sessions.csv" in name or "trials_and_sessions.xlsx" in name:
                    trials_file = f
                    break

            if trials_file is None:
                raise Exception("No trials_and_sessions file found online in the folder.")

            trials_file_id = trials_file.get("id")
            trials_drive_id = trials_file.get("parentReference", {}).get("driveId")
            suffix = ".csv" if trials_file.get("name", "").lower().endswith(".csv") else ".xlsx"
            temp_trials_path = download_file_to_temp(self.onedrive_token, trials_drive_id, trials_file_id, suffix=suffix)
            if suffix == ".csv":
                df = pd.read_csv(temp_trials_path)
            else:
                df = pd.read_excel(temp_trials_path)
            for column in OBLIGATORY_COLUMNS:
                if column not in df:
                    df[column] = ""
            if self.language_code not in NO_LATIN:
                df["transcription_original_script"] = ""
                df["transcription_original_script_utterance_used"] = ""

            temp_output_trials = os.path.join(tempfile.gettempdir(), "trials_and_sessions_annotated.xlsx")

            # Find all audio files in the "binaries" folder.
            audio_files = recursive_list_files(self.onedrive_token, self.drive_id, self.input_dir)
            if not audio_files:
                raise Exception("No audio files found in the 'binaries' folder.")

            print("Audio files found:", [f.get("name") for f in audio_files])
            count = 0  # Initialize count here!
            for file in tqdm(audio_files, desc="Transcribing online"):
                count += 1
                file_id = file.get("id")
                file_name = file.get("name")
                file_drive_id = file.get("parentReference", {}).get("driveId")
                try:
                    suffix_audio = os.path.splitext(file_name)[1]
                    temp_path = download_file_to_temp(self.onedrive_token, file_drive_id, file_id, suffix=suffix_audio)
                    if self.language_code == 'zh':
                        result = self.model.transcribe(
                            temp_path,
                            language=self.language_code,
                            initial_prompt="请使用简体中文转录。"
                        )
                        transcription = result["text"].replace("请使用简体中文转录。", "").replace("使用简体中文转录。", "")
                    else:
                        result = self.model.transcribe(temp_path, language=self.language_code)
                        transcription = result["text"]
                    transcription = clean_string(transcription)
                    if verbose:
                        tqdm.write(transcription)
                    self.add_transcription_to_df(df, file_name, transcription, count, filename_regexp)
                except Exception as e:
                    logger.error(f"Error processing online file '{file_name}': {e}")
                    continue
                finally:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)

            df.to_excel(temp_output_trials, index=False)
            self.format_excel_output(temp_output_trials)
            logger.info("Transcription and annotation completed for online processing.")
            upload_file_to_onedrive(self.onedrive_token, self.drive_id, self.input_dir, temp_output_trials, "trials_and_sessions_annotated.xlsx")
            os.remove(temp_trials_path)

def main():
    parser = argparse.ArgumentParser(description="Automatic transcription")
    parser.add_argument("input_dir", help="Local directory or OneDrive folder ID containing audio and trials files")
    parser.add_argument("language", help="Language of the audio content")
    parser.add_argument("--verbose", action="store_true", help="Print detailed output")
    parser.add_argument("--onedrive_token", help="OneDrive access token (if processing online)")
    parser.add_argument("--drive_id", help="OneDrive drive ID (if processing online)")
    args = parser.parse_args()

    transcriber = Transcriber(args.input_dir, args.language, onedrive_token=args.onedrive_token, drive_id=args.drive_id)
    transcriber.process_data(verbose=args.verbose)

if __name__ == "__main__":
    main()