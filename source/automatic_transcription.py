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
import whisper
import warnings
import argparse
import string
import pandas as pd
from tqdm import tqdm
from transliterate import translit
import cutlet
import json


# Suppress warnings that can clutter output, use this cautiously as it might hide important warnings
warnings.filterwarnings("ignore")

# Load and initialize the Whisper model for audio processing
model = whisper.load_model("large-v3")

# Store the current working directory for relative path calculations
current_dir = os.getcwd()
# Compute the absolute file path for the language configurations
file_path = os.path.abspath(os.path.join(current_dir, 'materials', 'LANGUAGES'))

# Load language configurations from a JSON file
with open(file_path, 'r', encoding='utf-8') as file:
    LANGUAGES = json.load(file)

def __process_string(input_string):
    """
    Process a string by converting it to lowercase and removing punctuation.

    Parameters:
        input_string (str): The string to be processed.

    Returns:
        str: The processed string.
    """
    lowercase_string = input_string.lower()

    translator = str.maketrans("", "", string.punctuation)
    processed_string = lowercase_string.translate(translator)

    return processed_string


def process_data(directory, language, latin_transliteration = False):
    """
    This functions iterates over a given directory and looks for a 'binaries' folder,
    containing audio data. The function takes as input then the trials and sessions
    csv file and the binares linked to it and perfoms automatic transcription using 
    the model Whisper from OpenAI for a given language.
    
    For each audio file, the program looks for its name inside the csv and 
    according its to row index, it transcribes the audio and postprocess the text
    to delete punctuation. It also keeps track of the number of transcription
    in case there are 2 audio files for task, in order to not overwrite.
    The program writes the final text in a column named automatic_transcription
    in the previously found row index.
    It can also perform transliteration if asked for.
    
    

    Parameters:
        directory (str): Path to the input directory.
    """
    try:
        for subdir, dirs, files in os.walk(directory):
            if 'binaries' in subdir:
                csv_file_path = os.path.join(subdir, '..', 'trials_and_sessions.csv')
                excel_file_path = os.path.join(subdir, '..', 'trials_and_sessions.xlsx')
                excel_output_file = os.path.join(subdir, '..', 'trials_and_sessions_annotated.xlsx')
                if os.path.exists(csv_file_path):
                    df = pd.read_csv(csv_file_path)
                elif os.path.exists(excel_file_path):
                    df = pd.read_excel(excel_file_path)
                
                #add columns for workflow
                new_columns = ["personal_data_free_check",
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
                for column in new_columns:
                    if column not in df:
                        df[column] = ""
                    
                count = 0
                for file in tqdm(files, desc=f"Processing Files in subdir {subdir}", unit="file"):
                    if file.endswith('.mp3'):
                        count += 1
                        audio_file_path = os.path.abspath(os.path.join(subdir, file))
                        transcription = ""
                        transcription = model.transcribe(audio_file_path, language = language)
                        transcription = __process_string(transcription["text"])
                        print(transcription)

                        series = df[df.isin([file])].stack()
                        for idx, value in series.items():
                            df.at[idx[0], "automatic_transcription"] += f"{count}: {transcription}"
                        
                        if latin_transliteration:
                            if language == "ru":
                                for idx, value in series.items():
                                    df.at[idx[0], "latin_transcription_everything"] += f"{count}: {translit(transcription, 'ru',reversed=True)}"
                            elif language == "uk":
                                for idx, value in series.items():
                                    df.at[idx[0], "latin_transcription_everything"] += f"{count}: {translit(transcription, 'uk',reversed=True)}"
                            elif language == "ja":
                                katsu = cutlet.Cutlet()
                                for idx, value in series.items():
                                    df.at[idx[0], "latin_transcription_everything"] += f"{count}: {katsu.romaji(transcription)}"

                df.to_excel(excel_output_file)
                print(f"\nTranscription and translation completed for {subdir}.")
    except Exception as e:
        print(f"An error occurred: {str(e)}")


def main():
    """
    Main function to parse command line arguments and initiate data processing.
    """
    parser = argparse.ArgumentParser(description="automatic transcription")
    parser.add_argument("input_dir")
    parser.add_argument("language", default=None, help="Language of the audio content")
    parser.add_argument("--transliteration", action="store_true", help="Perform transliteration into latin alphabet for Japanese and Russian")
    args = parser.parse_args()
    
    language = args.language
    if language:
        for code, name in LANGUAGES.items():
            if name == args.language.lower():
                language = code
        print(f"language recognized. Transcribing for {language}")
    else:
        print("No Language given. Language will automatically recognized")
        
    process_data(args.input_dir, language, args.transliteration)

if __name__ == "__main__":
    main()

