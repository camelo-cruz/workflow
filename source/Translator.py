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
from deep_translator import GoogleTranslator
from functions import set_global_variables, find_language

LANGUAGES, NO_LATIN, OBLIGATORY_COLUMNS, _ = set_global_variables()

class Translator():
    def __init__(self,input_dir, language, instruction=None):
        self.input_dir = input_dir
        self.language_code = find_language(language, LANGUAGES)
        self.instruction = instruction

    def process_data(self):
        automatic_column = "automatic_transcription"
        corrected_column = "latin_transcription_everything"
        sentences_column = "latin_transcription_utterance_used"
        
        for i in range(len(df)):
            for subdir, dirs, files in os.walk(self.input_dir):
                for file in files:
                    if file.endswith('annotated.xlsx'):
                        file = os.path.join(subdir, file)
                        df = pd.read_excel(file)
                        try:
                            if not self.instruction:
                                df.loc[i,"translation_everything"] = GoogleTranslator(source=self.language, target='en').translate(df[corrected_column][i])
                            elif self.instruction == 'automatic_transcription':
                                df.loc[i,"automatic_translation"] = GoogleTranslator(source=self.language, target='en').translate(df[automatic_column][i])
                            elif self.instruction == 'sentences':
                                df.loc[i,"translation_utterance_used"] = GoogleTranslator(source=self.language, target='en').translate(df[sentences_column][i])
                        except Exception as e:
                            print(f"An error occurred: {str(e)}")
                df.to_excel(file)
                
        return df


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
    parser.add_argument("--instruction", 
                        choices=["automatic_transcription", 
                                 "corrected_transcription", 
                                 "sentences"], 
                        help="Type of instruction for translation", required=False)
    args = parser.parse_args()

    translator = Translator(args.input_dir, args.language, args.instruction)
    translator.process_data()

if __name__ == "__main__":
    main()