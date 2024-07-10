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

OBLIGATORY = [
    "personal_data_free_check", 
    "automatic_transcription", 
    "latin_transcription_everything",
    "latin_transcription_utterance_used", 
    "transcription_comment", 
    "transcription_check",
    "automatic_translation", 
    "translation_everything", 
    "translation_utterance_used",
    "translation_comment", 
    "translation_check", 
    "transcription_morphosegmentation", 
    "automatic_glossing", 
    "glossing_utterance_used", 
    "glossing_comment"
]

MAPPING = {
    "latin_transcription_everything": "transcription",
    "translation_everything": "translation",
    "latin_transcription_utterance_used": "glossing_object_language",
    "transcription_morphosegmentation": "glossing_object_language",
    "glossing_utterance_used": "glossing_meta_language"
    }


def process_data(directory):
    for subdir, dirs, files in os.walk(directory):
        excel_file_path = os.path.join(subdir, 'trials_and_sessions_annotated.xlsx')
        try:
            if os.path.exists(excel_file_path):
                df = pd.read_excel(excel_file_path)
                print(f'processing {excel_file_path}')
                df = update_columns(df)
                df = reorder_columns(df)
                
                df.to_excel(excel_file_path, index=False)
        except Exception as e:
            print(f"Error processing the file {excel_file_path}: {e}")

def update_columns(df):
    for column in OBLIGATORY:
        if column not in df.columns:
            df[column] = ''

    for new_col, old_col in MAPPING.items():
        if old_col in df.columns:
            df[new_col] = df[old_col]

    try:
        if 'latin_transcription_utterance_used' in df.columns:
            df['latin_transcription_utterance_used'] = df['latin_transcription_utterance_used'].str.replace('-', '', regex=True)
    except Exception as e:
        print(f"Handled error: {e} - Continuing with other operations.")

    return df


def reorder_columns(df):
    additional_columns = [col for col in df.columns if col not in OBLIGATORY]
    new_column_order = additional_columns + OBLIGATORY
    return df[new_column_order]

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="automatic transcription")
    parser.add_argument("input_dir")
    
    args = parser.parse_args()
    process_data(args.input_dir)


