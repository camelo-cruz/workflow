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
from deep_translator import GoogleTranslator
import argparse
import json

current_dir = os.getcwd()
file_path = os.path.join(current_dir, 'materials', 'LANGUAGES')

with open(file_path, 'r', encoding='utf-8') as file:
    LANGUAGES = json.load(file)

def translate(file, instruction, source_language):
    df = pd.read_excel(file)
    
    for i in range(len(df)):
        try:
            if instruction == 'corrected':
                df.loc[i,"automatic_translation"] = GoogleTranslator(source=source_language, target='en').translate(df["latin_transcription_everything"][i])
            elif instruction == 'automatic_transcription':
                df.loc[i,"automatic_translation"] = GoogleTranslator(source=source_language, target='en').translate(df["automatic_transcription"][i])
            elif instruction == 'sentences':
                df.loc[i,"translation_utterance_used"] = GoogleTranslator(source=source_language, target='en').translate(df["latin_transcription_utterance_used"][i])
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            
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
    parser.add_argument("instruction", choices=["automatic_transcription", 
                                                "corrected","sentences"], 
                        help="Type of instruction for processing.")
    parser.add_argument("source_language")
    args = parser.parse_args()
    
    language = None
    for code, name in LANGUAGES.items():
        if name == args.source_language.lower():
            language = code
    
    for subdir, dirs, files in os.walk(args.input_dir):
        for file in files:
            if file.endswith('annotated.xlsx'):
                file = os.path.join(subdir, file)
                df = translate(file, args.instruction, language)
                df.to_excel(file)


if __name__ == "__main__":
    main()