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
import tempfile
import warnings
import logging
import sys
import argparse
import torch
import openpyxl
import whisper
import whisperx
import pandas as pd
from tqdm import tqdm
from whisperx.diarize import DiarizationPipeline
from dotenv import load_dotenv
from openpyxl.styles import Font

from ..utils.functions import (set_global_variables, 
                                find_language, 
                                clean_string, 
                                find_ffmpeg, 
                                format_excel_output, 
                                setup_logging)

# Set global variables and suppress warnings
LANGUAGES, NO_LATIN, OBLIGATORY_COLUMNS, _ = set_global_variables()
warnings.filterwarnings("ignore")

# Configure global logger
timestamp = "%Y-%m-%d %H:%M:%S"
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Console handler: show all logs
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(logging.Formatter(f"%(asctime)s - %(levelname)s - %(message)s", datefmt=timestamp))
logger.addHandler(console_handler)

ffmpeg_path = find_ffmpeg()

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)


class Transcriber:
    def __init__(self, input_dir, language, device=None, drive_id=None, onedrive_token=None):
        self.input_dir = input_dir
        self.language_code = find_language(language, LANGUAGES)
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.batch_size = 8
        self.drive_id = drive_id
        self.onedrive_token = onedrive_token

        # Determine materials path
        try:
            base_path = os.path.join(sys._MEIPASS, 'materials')
            logger.debug("Using sys._MEIPASS for materials path: %s", base_path)
        except AttributeError:
            base_path = os.path.join(parent_dir, 'materials')
            logger.debug("Using script directory for materials path: %s", base_path)

        # Load Hugging Face key
        self.hugging_key = os.getenv("HUGGING_KEY")
        if not self.hugging_key:
            secrets_path = os.path.join(base_path, 'secrets.env')
            if os.path.exists(secrets_path):
                load_dotenv(secrets_path, override=True)
                self.hugging_key = os.getenv("HUGGING_KEY")

        if not self.hugging_key:
            logger.error("Hugging Face key not found. Set it in environment or materials/secrets.env")
            raise ValueError("Hugging Face key not found. Set it in environment or materials/secrets.env")

        logger.debug("Using Hugging Face token: %s...", self.hugging_key[:10])

    def load_trials_data(self, base_dir):
        """
        Load the trials and sessions data from CSV or Excel.
        Returns the dataframe and the path for the annotated Excel output.
        """
        csv_file = os.path.join(base_dir, 'trials_and_sessions.csv')
        excel_file = os.path.join(base_dir, 'trials_and_sessions.xlsx')
        excel_out = os.path.join(base_dir, 'trials_and_sessions_annotated.xlsx')

        if os.path.exists(csv_file):
            df = pd.read_csv(csv_file)
        elif os.path.exists(excel_file):
            df = pd.read_excel(excel_file)
        else:
            logger.error("No trials_and_sessions file found in %s", base_dir)
            raise FileNotFoundError("No trials_and_sessions file found in the directory.")

        for col in OBLIGATORY_COLUMNS:
            if col not in df:
                df[col] = ""
        if self.language_code not in NO_LATIN:
            df.update({
                "transcription_original_script": "",
                "transcription_original_script_utterance_used": ""
            })

        return df, excel_out

    def _append_to_cell(self, df, idx, column, text):
        """Helper to append text to a DataFrame cell, initializing if empty."""
        old_val = df.at[idx, column]
        df.at[idx, column] = ("" if pd.isna(old_val) else old_val) + text

    def add_transcription_to_df(self, df, file, transcription, count, filename_regexp):
        # Locate and append transcription in DataFrame cells
        series = df[df.isin([file])].stack()
        is_nonlatin = self.language_code in NO_LATIN
        text_auto = f"{count}: {transcription}"
        text_suffix = " - " if series.empty else " "
        global col_name
        col_name = ('transcription_original_script' if is_nonlatin else 'latin_transcription_everything')

        if series.empty:
            match = filename_regexp.search(file)
            if not match:
                logger.warning("File '%s' does not match pattern. Skipping.", file)
                return

            blk, tsk, trl = map(int, (match.group('block'), match.group('task'), match.group('trial')))
            cond = (
                (df['Block_Nr'] == blk) &
                (df['Task_Nr'] == tsk) &
                (df['Trial_Nr'] == trl)
            )
            if df.loc[cond].empty:
                logger.warning("No row for block %d, task %d, trial %d. Skipping '%s'.", blk, tsk, trl, file)
                return

            col_ctr = 1
            miss_col = f'missing_filename_{col_ctr}'
            while miss_col in df.columns and not df.loc[cond, miss_col].isna().all():
                col_ctr += 1
                miss_col = f'missing_filename_{col_ctr}'
            df.loc[cond, miss_col] = file

            for idx in df.loc[cond].index:
                self._append_to_cell(df, idx, 'automatic_transcription', text_auto + text_suffix)
                self._append_to_cell(df, idx, col_name, text_auto + text_suffix)
        else:
            for (row_idx, _), _ in series.items():
                self._append_to_cell(df, row_idx, 'automatic_transcription', text_auto + text_suffix)
                self._append_to_cell(df, row_idx, col_name, text_auto + text_suffix)

    def transcribe_and_diarize(self, path_to_audio):
        if self.language_code == 'zh':
            model = whisper.load_model("large-v2", device=self.device)
            res = model.transcribe(path_to_audio, language='zh', initial_prompt="请使用简体中文转录。")
            return res["text"].replace("请使用简体中文转录。", "").strip()

        if self.language_code == 'bn':
            model = whisper.load_model("large-v2", device=self.device)
            return model.transcribe(path_to_audio, language=self.language_code)["text"]

        model = None
        try:
            model = whisperx.load_model("large-v2", self.device, compute_type="float16", language=self.language_code)
        except RuntimeError:
            model = whisperx.load_model("large-v2", self.device, compute_type="int8", language=self.language_code)

        audio = whisperx.load_audio(path_to_audio)
        result = model.transcribe(audio, batch_size=self.batch_size, language=self.language_code)

        align_model, metadata = whisperx.load_align_model(language_code=result["language"], device=self.device)
        result = whisperx.align(result["segments"], align_model, metadata, audio, self.device, return_char_alignments=False)

        diarizer = DiarizationPipeline(model_name="pyannote/speaker-diarization-3.1", use_auth_token=self.hugging_key, device=self.device)
        diarize_segments = diarizer(audio)
        result = whisperx.assign_word_speakers(diarize_segments, result)

        sentences, buf_spk, buf_txt = [], None, ""
        for seg in result["segments"]:
            spk = seg.get("speaker", buf_spk)
            if spk is None: continue
            txt = seg["text"].strip()
            if buf_spk is None:
                buf_spk, buf_txt = spk, txt
            elif spk == buf_spk:
                buf_txt += " " + txt
            else:
                sentences.append(f"{buf_spk}: {buf_txt}")
                buf_spk, buf_txt = spk, txt
        if buf_spk:
            sentences.append(f"{buf_spk}: {buf_txt}")

        return "  ".join(sentences)

    def process_data(self, verbose=True):
        filename_regexp = re.compile(r'blockNr_(?P<block>\d+)_taskNr_(?P<task>\d+)_trialNr_(?P<trial>\d+).*')
        for subdir, _, files in os.walk(self.input_dir):
            if 'binaries' not in subdir:
                continue
            logger.info("Processing directory: %s", subdir)
            base = os.path.abspath(os.path.join(subdir, '..'))
            log_path = os.path.join(base, "transcription.log")
            fh = setup_logging(log_path)

            try:
                df, out_file = self.load_trials_data(base)
            except FileNotFoundError as e:
                logger.error(e)
                logger.removeHandler(fh)
                fh.close()
                continue

            count = 0
            files.sort()
            for file in tqdm(files, desc="Transcribing", unit="file"):
                if not file.lower().endswith(('.mp3', '.mp4', '.m4a')):
                    continue
                count += 1
                path = os.path.abspath(os.path.join(subdir, file))
                logger.debug("Transcribing file %d/%d: %s", count, len(files), path)
                try:
                    text = self.transcribe_and_diarize(path)
                    text = clean_string(text)
                    if verbose:
                        logger.info(text)
                    self.add_transcription_to_df(df, file, text, count, filename_regexp)
                except Exception as e:
                    logger.error("Error on '%s': %s", file, e)
                    continue
            df.to_excel(out_file, index=False)
            format_excel_output(out_file, [col_name])
            logger.info("Completed processing: %s", subdir)
            logger.removeHandler(fh)
            fh.close()
