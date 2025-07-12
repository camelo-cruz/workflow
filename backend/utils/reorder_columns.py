#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Copyright (C) 2024  Alejandra Camelo Cruz

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
        
Leibniz Institute General Linguistics (ZAS)
"""

import os
import pandas as pd
import argparse
import json

file_dir = os.path.dirname(os.path.abspath(__file__))
columns_path = os.path.abspath(os.path.join(file_dir, '..', 'materials', 'OBLIGATORY_COLUMNS'))
nolatin_path = os.path.abspath(os.path.join(file_dir, '..', 'materials', 'NO_LATIN'))
languages_path = os.path.abspath(os.path.join(file_dir,'..', 'materials', 'LANGUAGES'))

MAPPING = {
    "latin_transcription_everything": "transcription",
    "translation_everything": "translation",
    "latin_transcription_utterance_used": "glossing_object_language",
    "transcription_morphosegmentation": "glossing_object_language",
    "glossing_utterance_used": "glossing_meta_language",
    "transcription_comment": "transcription_comments",
    "translation_comment": "translation_comments",
    "glossing_comment": "glossing_comments"
    }

with open(languages_path, 'r', encoding='utf-8') as file:
    LANGUAGES = json.load(file)

with open(columns_path, 'r', encoding='utf-8') as file:
    OBLIGATORY_COLUMNS = file.read().splitlines()

with open(nolatin_path, 'r', encoding='utf-8') as file:
    NO_LATIN = file.read().splitlines()

def update_columns(df):
    for column in OBLIGATORY_COLUMNS:
        if column not in df.columns:
            df[column] = ''

    for new_col, old_col in MAPPING.items():
        if old_col in df.columns:
            df[new_col] = df[old_col]
            df = df.drop(old_col, axis=1)

    try:
        if 'latin_transcription_utterance_used' in df.columns:
            df['latin_transcription_utterance_used'] = df['latin_transcription_utterance_used'].str.replace('-', '', regex=True)
    except Exception as e:
        print(f"Handled error: {e} - Continuing with other operations.")

    return df

def reorder_columns(df, language):
    additional_columns = [col for col in df.columns if col not in OBLIGATORY_COLUMNS]
    new_column_order = additional_columns + OBLIGATORY_COLUMNS
    for key, val in LANGUAGES.items():
        if val == language:
            language = key
    if language not in NO_LATIN:
        new_column_order.remove('transcription_original_script')
        new_column_order.remove('transcription_original_script_utterance_used')
    return df[new_column_order]

def process_columns(directory, language):
    for subdir, dirs, files in os.walk(directory):
        excel_file_path = os.path.join(subdir, 'trials_and_sessions_annotated.xlsx')
        csv_file_path = os.path.join(subdir, 'trials_and_sessions.csv')
        try:
            if os.path.exists(excel_file_path):
                df = pd.read_excel(excel_file_path)
                print(f'processing {excel_file_path}')
                df = update_columns(df)
                df = reorder_columns(df, language)
                df.to_excel(excel_file_path, index=False)
            elif os.path.exists(csv_file_path):
                df = pd.read_csv(csv_file_path)
                print(f'processing {csv_file_path}')
                df = update_columns(df)
                df = reorder_columns(df, language)
                df.to_excel(excel_file_path, index=False)
        
        except Exception as e:
            print(f"Error processing the file {excel_file_path}: {e}")

def create_columns(directory, language):
    print(f'Processing dir {directory}')
    for subdir, dirs, files in os.walk(directory):
        for filename in files:
            if filename.endswith('.csv'):
                csv_file_path = os.path.join(subdir, filename)
                print(f'Processing {csv_file_path}')
                excel_file_name = filename.replace('.csv', '_annotated.xlsx')
                excel_file_path = os.path.join(subdir, excel_file_name)
                try:
                    df = pd.read_csv(csv_file_path)
                    df = update_columns(df)
                    df = reorder_columns(df, language)
                    df.to_excel(excel_file_path, index=False)
                except Exception as e:
                    print(f"Error processing the file {csv_file_path}: {e}")


