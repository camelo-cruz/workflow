#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Copyright (C) 2024  Alejandra Camelo Cruz, Arne Goelz

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Leibniz Institute General Linguistics (ZAS)
"""

import os
import re
import sys
import torch
import logging
import warnings
import pandas as pd
from tqdm import tqdm
from dotenv import load_dotenv
from whisperx.diarize import DiarizationPipeline
from openpyxl.styles import Font

import whisper
import whisperx

from ..utils.functions import (
    set_global_variables,
    find_language,
    clean_string,
    find_ffmpeg,
    setup_logging,
    format_excel_output
)

# Global setup
LANGUAGES, NO_LATIN, OBLIGATORY_COLUMNS, _ = set_global_variables()
warnings.filterwarnings("ignore")

logger = logging.getLogger(__name__)

ffmpeg_path = find_ffmpeg()

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)


class Transcriber:
    def __init__(self, input_dir, language, device=None):
        self.input_dir = input_dir
        self.language_code = find_language(language, LANGUAGES)
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.batch_size = 8
        self.hugging_key = self._load_hugging_face_token()

    def _load_hugging_face_token(self):
        token = os.getenv("HUGGING_KEY")
        if not token:
            secrets_path = os.path.join(parent_dir, 'materials', 'secrets.env')
            if os.path.exists(secrets_path):
                load_dotenv(secrets_path, override=True)
                token = os.getenv("HUGGING_KEY")
        if not token:
            raise ValueError("Hugging Face key not found. Set it in Hugging Face Secrets or in materials/secrets.env")
        logger.info(f"Using Hugging Face token: {token[:10]}...")
        return token
    
    def _append_to_cell(self, df, idx, column, text):
        old_val = df.at[idx, column]
        df.at[idx, column] = ("" if pd.isna(old_val) else old_val) + text

    def load_trials_data(self, base_dir):
        csv_file = os.path.join(base_dir, 'trials_and_sessions.csv')
        excel_file = os.path.join(base_dir, 'trials_and_sessions.xlsx')
        excel_out = os.path.join(base_dir, 'trials_and_sessions_annotated.xlsx')

        if os.path.exists(csv_file):
            df = pd.read_csv(csv_file)
        elif os.path.exists(excel_file):
            df = pd.read_excel(excel_file)
        else:
            raise FileNotFoundError("No trials_and_sessions file found in the directory.")

        for col in OBLIGATORY_COLUMNS:
            df[col] = df.get(col, "")

        if self.language_code not in NO_LATIN:
            df["transcription_original_script"] = ""
            df["transcription_original_script_utterance_used"] = ""

        return df, excel_out

    def add_transcription_to_df(self, df, file, transcription, count, filename_regexp):
        series = df[df.isin([file])].stack()
        text_auto = f"{count}: {transcription}"
        text_suffix = " - " if series.empty else " "
        col_name = 'transcription_original_script' if self.language_code in NO_LATIN else 'latin_transcription_everything'

        if series.empty:
            match = filename_regexp.search(file)
            if not match:
                logger.warning(f"File '{file}' does not match block/task/trial pattern. Skipping.")
                return

            blk, tsk, trl = int(match['block']), int(match['task']), int(match['trial'])
            cond = (df['Block_Nr'] == blk) & (df['Task_Nr'] == tsk) & (df['Trial_Nr'] == trl)
            if df.loc[cond].empty:
                logger.warning(f"No row for block {blk}, task {tsk}, trial {trl}. Skipping '{file}'.")
                return

            miss_col = next(f"missing_filename_{i}" for i in range(1, 10) if f"missing_filename_{i}" not in df.columns or df.loc[cond, f"missing_filename_{i}"].isna().all())
            df.loc[cond, miss_col] = file
            for idx in df.loc[cond].index:
                self._append_to_cell(df, idx, 'automatic_transcription', text_auto + text_suffix)
                self._append_to_cell(df, idx, col_name, text_auto + text_suffix)
        else:
            for (row_idx, _), _ in series.items():
                self._append_to_cell(df, row_idx, 'automatic_transcription', text_auto + text_suffix)
                self._append_to_cell(df, row_idx, col_name, text_auto + text_suffix)

    def transcribe_and_diarize(self, path_to_audio):
        if self.language_code in ['en', 'fr', 'de', 'es', 'it', 'ja', 'nl', 'uk', 'pt', 'ar', 'cs',
                             'ru', 'pl', 'hu', 'fi', 'fa', 'el', 'tr', 'da', 'he', 'vi', 'ko',
                             'ur', 'te', 'hi', 'ca', 'ml', 'no', 'nn', 'sk', 'sl', 'hr', 'ro',
                             'eu', 'gl', 'ka', 'lv', 'tl', 'zh']:
            model = None
            try:
                model = whisperx.load_model("large-v2", self.device, compute_type="float16", language=self.language_code)
            except:
                model = whisperx.load_model("large-v2", self.device, compute_type="int8", language=self.language_code)
            audio = whisperx.load_audio(path_to_audio)
            result = model.transcribe(audio, batch_size=self.batch_size, language=self.language_code)

            model_a, metadata = whisperx.load_align_model(language_code=result["language"], device=self.device)
            result = whisperx.align(result["segments"], model_a, metadata, audio, self.device)

            diarize_model = DiarizationPipeline(model_name="pyannote/speaker-diarization-3.1", use_auth_token=self.hugging_key, device=self.device)
            diarize_segments = diarize_model(audio)
            result = whisperx.assign_word_speakers(diarize_segments, result)

            full_sentences, buffer_speaker, buffer_text = [], None, ""
            for seg in result["segments"]:
                spk = seg.get("speaker", buffer_speaker)
                if spk is None: continue
                txt = seg["text"].strip()

                if buffer_speaker is None:
                    buffer_speaker, buffer_text = spk, txt
                elif spk == buffer_speaker:
                    buffer_text += " " + txt
                else:
                    full_sentences.append(f"{buffer_speaker}: {buffer_text}")
                    buffer_speaker, buffer_text = spk, txt

            if buffer_speaker:
                full_sentences.append(f"{buffer_speaker}: {buffer_text}")

        else:
            model = whisper.load_model("large-v2", self.device)
            res = model.transcribe(path_to_audio, language=self.language_code)
            return res["text"]

        return "  ".join(full_sentences)

    def process_data(self, verbose=True):
        filename_regexp = re.compile(r'blockNr_(?P<block>\d+)_taskNr_(?P<task>\d+)_trialNr_(?P<trial>\d+).*')

        for subdir, _, files in os.walk(self.input_dir):
            if 'binaries' not in subdir:
                continue

            base = os.path.abspath(os.path.join(subdir, '..'))
            log_path = os.path.join(base, "transcription.log")
            fh = setup_logging(logger, log_path)
            logger.info(f"Processing directory: {base}")

            try:
                df, out_file = self.load_trials_data(base)
            except FileNotFoundError as e:
                logger.error(e)
                logger.removeHandler(fh)
                fh.close()
                continue

            count = 0
            files.sort()
            for file in tqdm(files, desc="Transcribing"):
                if not file.lower().endswith(('.mp3', '.mp4', '.m4a')):
                    continue
                count += 1
                path = os.path.abspath(os.path.join(subdir, file))
                logger.info(f"Processing file: {file} ({count}/{len(files)})")
                try:
                    text = self.transcribe_and_diarize(path)
                    if self.language_code == 'de':
                        text = clean_string(text)
                    if verbose:
                        tqdm.write(text)
                    self.add_transcription_to_df(df, file, text, count, filename_regexp)
                except Exception as e:
                    logger.error(f"Error on '{file}': {e}")
            df.to_excel(out_file, index=False)
            format_excel_output(out_file, 'transcription_original_script' if self.language_code in NO_LATIN else 'latin_transcription_everything')
            logger.removeHandler(fh)
            fh.close()
