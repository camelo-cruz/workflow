# -*- coding: utf-8 -*-
"""
Copyright (C) 2024  Alejandra Camelo Cruz, Arne Goelz

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
import torch
import re
import sys
import deepl
import logging
import time
import deepl
from dotenv import load_dotenv 
from deep_translator import GoogleTranslator
from tqdm import tqdm
import openpyxl
from openpyxl.styles import Font
from utils.functions import set_global_variables, find_language
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

def setup_logging(log_file_path):
    """Dynamically updates logging to write to a new log file."""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)  # Set the root logger's level to INFO
    
    # Remove existing handlers to avoid duplicate logs
    if logger.hasHandlers():
        logger.handlers.clear()

    # Create a file handler for the new log file
    file_handler = logging.FileHandler(log_file_path, mode="a")  # "a" = append mode
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

    # Create a console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

    # Add both handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    logging.info(f"Logging started for {log_file_path}")

LANGUAGES, NO_LATIN, OBLIGATORY_COLUMNS, _ = set_global_variables()


class Translator():
    def __init__(self, input_dir, language, instruction, device="cpu"):
        self.input_dir = input_dir
        self.language_code = find_language(language, LANGUAGES)
        self.instruction = instruction
        self.device = device

        logging.info(f"Initialized Translator for language: {language} (code: {self.language_code}) (instruction: {instruction})")

    @staticmethod
    def translate_with_pretrained(language_code, text, device="cpu"):
        """ Translates text using the NLLB-200 model """
        start_time = time.time()
        model = AutoModelForSeq2SeqLM.from_pretrained("facebook/nllb-200-1.3B").to(device)
        tokenizer = AutoTokenizer.from_pretrained("facebook/nllb-200-1.3B", src_lang=f'{language_code}_Latn')
        inputs = tokenizer(text, return_tensors="pt").to(device)
        translated_tokens = model.generate(
            **inputs, forced_bos_token_id= tokenizer.convert_tokens_to_ids("eng_Latn")
        )

        translated = tokenizer.batch_decode(translated_tokens, skip_special_tokens=True)[0]
        end_time = time.time()

        logging.info(f"Translated with NLLB-200 in {end_time - start_time:.2f} seconds")
        return translated
    
    @staticmethod
    def translate_with_deepl(language_code, text):
        """ Translates text using DeepL API, ensuring correct language codes """
        try:
            # If running under PyInstaller, sys._MEIPASS is available
            base_path = os.path.join(sys._MEIPASS, 'materials')
            print("Using sys._MEIPASS for materials path")
        except Exception:
            # Fallback to using the script's directory if not running as a PyInstaller bundle
            script_dir = os.path.dirname(os.path.abspath(__file__))
            base_path = os.path.join(script_dir, 'materials')
            print("Using script directory for materials path")

        secrets_path = os.path.join(base_path, 'secrets.env')

        if os.path.exists(secrets_path):
            load_dotenv(secrets_path, override=True)
        else:
            print(f"Error: {secrets_path} not found.")
            sys.exit(1)
        
        api_key = os.getenv("API_KEY")
        if not api_key:
            raise ValueError("API key not found. Check your secrets.env file.")

        deepl_client = deepl.DeepLClient(api_key)
        
        # Handle "PT" separately
        if language_code.lower() == "pt":
            language_code = "PT-BR"  # Default to Brazilian Portuguese

        source_lang = language_code.upper()  # Ensure uppercase

        try:
            result = deepl_client.translate_text(text, source_lang=source_lang, target_lang='EN-US')
        except deepl.DeepLException:
            result = deepl_client.translate_text(text, target_lang='EN-US')

        return result.text

    def process_data(self, verbose=False):
        """ Processes and translates data from input Excel files """
        logging.info(f"Starting translation process for directory: {self.input_dir}")
        start_time = time.time()

        automatic_column = "automatic_transcription"
        corrected_column = "latin_transcription_everything"
        sentences_column = "latin_transcription_utterance_used"

        if self.language_code in NO_LATIN:
            corrected_column = "transcription_original_script"
            sentences_column = "transcription_original_script_utterance_used"
        files_to_process = []
        for subdir, dirs, files in os.walk(self.input_dir):
            for file in files:
                if file.endswith('annotated.xlsx'):
                    files_to_process.append(os.path.join(subdir, file))
 
        with tqdm(total=len(files_to_process), desc="Processing files", unit="file") as file_pbar:
            for file_path in files_to_process:
                log_file = os.path.join(os.path.dirname(file_path), "translation.log")
                setup_logging(log_file)
                logging.info(f"Processing file: {file_path}")
                df = pd.read_excel(file_path)

                max_iterations = 100
                iteration_count = 0

                for i in range(len(df)):
                    if i >= max_iterations:
                        logging.info(f"Reached max iteration limit ({max_iterations}), exiting early.")
                        break

                    try:
                        text_to_translate = df.at[i, corrected_column if self.instruction == 'corrected' else
                                                        automatic_column if self.instruction == 'automatic' else
                                                        sentences_column]

                        if pd.isna(text_to_translate) or not str(text_to_translate).strip():
                            logging.info(f"Skipping row {i}: empty or whitespace value, raw value: {repr(text_to_translate)}")
                            continue

                        translation = None
                        if self.instruction in ['sentences', 'corrected']:
                            translation = GoogleTranslator(source=self.language_code, target='en').translate(text=text_to_translate)
                        elif self.instruction == 'automatic':
                            translation = self.translate_with_pretrained(self.language_code, text_to_translate, self.device)
                        
                        if not translation:
                            logging.info(f"Skipping row {i}: translation failed or empty")
                            continue

                        columns_mapping = {
                            'corrected': [
                                "automatic_translation_corrected_transcription",
                                "translation_everything"
                            ],
                            'automatic': [
                                "automatic_translation_automatic_transcription"
                            ],
                            'sentences': [
                                "automatic_translation_utterance_used",
                                "translation_utterance_used"
                            ]
                        }

                        for col in columns_mapping.get(self.instruction, []):
                            df.at[i, col] = translation

                        iteration_count += 1

                    except Exception as e:
                        logging.exception(f"Translation failed at row {i}: {e}")
                        continue

                # Reorder columns to ensure obligatory columns are at the end
                extra_columns = [col for col in df.columns if col not in OBLIGATORY_COLUMNS]
                df = df[extra_columns + [col for col in OBLIGATORY_COLUMNS if col in df.columns]]

                df.to_excel(file_path, index=False)

                # Open the Excel file and modify cell formatting
                wb = openpyxl.load_workbook(file_path)
                ws = wb.active  # Select the first sheet

                # Define the red font style
                red_font = Font(color="FF0000")  # Hex code for red color

                # Determine the target column name based on the instruction
                if self.instruction == 'automatic':
                    target_column = 'automatic_translation_automatic_transcription'
                if self.instruction == 'corrected':
                    target_column = 'translation_everything'
                elif self.instruction == 'sentences':
                    target_column = 'translation_utterance_used'
                else:
                    raise ValueError(f"Unsupported instruction: {self.instruction}")

                # Get the header row (first row) as a tuple of column names
                header_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True))

                # Ensure the target column exists in the header
                if target_column not in header_row:
                    raise ValueError(f"Target column '{target_column}' not found in header row.")

                # Find the column index (1-based) for the target column
                target_index = header_row.index(target_column) + 1

                # Apply red font to each cell in the target column (skip header row)
                for row in ws.iter_rows(min_row=2):
                    cell = row[target_index - 1]  # Adjust for 0-based indexing in row
                    if cell.value:
                        cell.font = red_font

                # Save the modified Excel file
                wb.save(file_path)

                file_pbar.update(1)

        end_time = time.time()
        logging.info(f"Translation process completed in {end_time - start_time:.2f} seconds")


def main():
    """ Main function to translate manually prepared transcriptions """
    parser = argparse.ArgumentParser(description="automatic transcription")
    parser.add_argument("input_dir")
    parser.add_argument("language")
    parser.add_argument("--instruction", "-i",
                        choices=["automatic_transcription",
                                 "corrected_transcription",
                                 "sentences"],
                        help="Type of instruction for translation", required=False)
    args = parser.parse_args()

    translator = Translator(args.input_dir, args.language, args.instruction)
    translator.process_data()


if __name__ == "__main__":
    main() 
