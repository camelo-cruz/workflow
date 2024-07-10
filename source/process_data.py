#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jul  3 18:17:22 2024

@author: alejandra
"""

import os
import pandas as pd
import argparse

obligatory_columns = [
    "personal_data_free_check", "automatic_transcription", "latin_transcription_everything",
    "latin_transcription_utterance_used", "transcription_comment", "transcription_check",
    "automatic_translation", "translation_everything", "translation_utterance_used",
    "translation_comment", "translation_check", "transcription_morphosegmentation", 
    "automatic_glossing", "glossing_utterance_used", "glossing_comment"
]


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
    # Ensure all obligatory columns exist in the DataFrame, add if not
    for column in obligatory_columns:
        if column not in df.columns:
            df[column] = ''

    mapping_columns = {
        "latin_transcription_everything": "transcription",
        "translation_everything": "translation",
        "latin_transcription_utterance_used": "glossing_object_language",
        "transcription_morphosegmentation": "glossing_object_language",
        "glossing_utterance_used": "glossing_meta_language"
    }


    # Map old columns to new columns and track old columns
    for new_col, old_col in mapping_columns.items():
        if old_col in df.columns:
            df[new_col] = df[old_col]

    # Remove hyphens from 'latin_transcription_utterance_used' if it exists
    try:
        if 'latin_transcription_utterance_used' in df.columns:
            # Convert to string to avoid issues with non-string data
            df['latin_transcription_utterance_used'] = df['latin_transcription_utterance_used'].str.replace('-', '', regex=True)
    except Exception as e:
        print(f"Handled error: {e} - Continuing with other operations.")

    return df


def reorder_columns(df):
    additional_columns = [col for col in df.columns if col not in obligatory_columns]
    new_column_order = additional_columns + obligatory_columns
    return df[new_column_order]

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="automatic transcription")
    parser.add_argument("input_dir")
    
    args = parser.parse_args()
    process_data(args.input_dir)


