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
from functions import set_global_variables, find_language
from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer

LANGUAGES, NO_LATIN, OBLIGATORY_COLUMNS, _ = set_global_variables()


class Translator():
    def __init__(self,input_dir, language, instruction=None):
        self.input_dir = input_dir
        self.language_code = find_language(language, LANGUAGES)
        self.instruction = instruction
        self.model = M2M100ForConditionalGeneration.from_pretrained("facebook/m2m100_1.2B")
        self.tokenizer = M2M100Tokenizer.from_pretrained("facebook/m2m100_1.2B")
    
    def translate_m2m100(self, text):
        """
        Translates text from a source language to English using the M2M100 model.

        Parameters:
            src_lang (str): The source language code.
            text (str): The text to be translated.
            model (transformers.M2M100ForConditionalGeneration): The M2M100 translation model.
            tokenizer (transformers.M2M100Tokenizer): The tokenizer associated with the M2M100 model.

        Returns:
            str: The translated text in English.
        """
        self.tokenizer.src_lang = self.language_code
        encoded_zh = self.tokenizer(text, return_tensors="pt")

        generated_tokens = self.model.generate(**encoded_zh, forced_bos_token_id=self.tokenizer.get_lang_id("en"))
        translated = self.tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)
        return " ".join(translated)

    def process_data(self):
        print("instruction", self.instruction)
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
                df = pd.read_excel(file_path)

                for i in range(len(df)):
                    print("translating row: ", i)
                    try:
                        if not self.instruction:
                            df.at[i, "automatic_translation_corrected_transcription"] = self.translate_m2m100(df[corrected_column].iloc[i])
                        elif self.instruction == 'automatic':
                            df.at[i, "automatic_translation_automatic_transcription"] = self.translate_m2m100(df[automatic_column].iloc[i])
                            print(f"translated {df[corrected_column].iloc[i]} {self.translate_m2m100(df[automatic_column].iloc[i])}")
                        elif self.instruction == 'corrected':
                            df.at[i, "automatic_translation_utterance_used"] = self.translate_m2m100(df[sentences_column].iloc[i])
                    except Exception as e:
                        print(f"Row {i} will not be translated")
                
                # Reorder columns to ensure obligatory columns are at the end
                extra_columns = [col for col in df.columns if col not in OBLIGATORY_COLUMNS]
                df = df[extra_columns + [col for col in OBLIGATORY_COLUMNS if col in df.columns]]

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