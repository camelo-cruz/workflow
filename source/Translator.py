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
from tqdm import tqdm
from functions import set_global_variables, find_language, translate_m2m100
from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer

LANGUAGES, NO_LATIN, OBLIGATORY_COLUMNS, _ = set_global_variables()

model = M2M100ForConditionalGeneration.from_pretrained("facebook/m2m100_1.2B")
tokenizer = M2M100Tokenizer.from_pretrained("facebook/m2m100_1.2B")

class Translator():
    def __init__(self,input_dir, language, instruction=None):
        self.input_dir = input_dir
        self.language_code = find_language(language, LANGUAGES)
        self.instruction = instruction

    def process_data(self):
        automatic_column = "automatic_transcription"
        corrected_column = "latin_transcription_everything"
        sentences_column = "latin_transcription_utterance_used"

        files_to_process = []
        for subdir, dirs, files in os.walk(self.input_dir):
            for file in files:
                if file.endswith('annotated.xlsx'):
                    files_to_process.append(os.path.join(subdir, file))

        with tqdm(total=len(files_to_process), desc="Processing files", unit="file") as file_pbar:
            for file_path in files_to_process:
                df = pd.read_excel(file_path)

                for i in range(len(df)):
                    try:
                        if not self.instruction:
                            df.at[i, "automatic_translation_corrected_transcription"] = translate_m2m100(self.language_code, df[corrected_column].iloc[i], model, tokenizer)
                        elif self.instruction == 'automatic_transcription':
                            df.at[i, "automatic_translation_automatic_transcription"] = translate_m2m100(self.language_code, df[automatic_column].iloc[i], model, tokenizer)
                        elif self.instruction == 'sentences':
                            df.at[i, "automatic_translation_utterance_used"] = translate_m2m100(self.language_code, df[sentences_column].iloc[i], model, tokenizer)
                    except Exception as e:
                        print(f"An error occurred while translating row {i}: {str(e)}")

                df.to_excel(file_path, index=False)

                file_pbar.update(1)


def main():
    """
    Main function to translate a manually prepaired transcription
    
    arguments:
        
        
    directory
    target language
    """
    
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