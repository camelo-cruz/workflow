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
from pydub import AudioSegment
from tqdm import tqdm
from transliterate import translit
import cutlet
import json


warnings.filterwarnings("ignore")
model = whisper.load_model("large-v3")
current_dir = os.getcwd()
file_path = os.path.join(current_dir, 'materials', 'LANGUAGES')

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


def __cut_audio(audiofile, start, end):
    """
    Cut a segment from an audio file based on start and end timestamps.

    Parameters:
        audiofile (str): Path to the input audio file.
        start (float): Start timestamp (in seconds) for the segment.
        end (float): End timestamp (in seconds) for the segment.

    Returns:
        str: Path to the output audio file containing the segment.
    """
    output = "tmp.wav"

    if audiofile.endswith('.wav'):
        sound = AudioSegment.from_wav(audiofile)  # for mp3: AudioSegment.from_mp3()
    elif audiofile.endswith('.mp3'):
        sound = AudioSegment.from_mp3(audiofile)

    StrtTime = float(start) * 1000
    EndTime = float(end) * 1000
    extract = sound[StrtTime:EndTime]

    # save
    extract.export(output, format="wav")

    return output


def process_data(directory, language, latin_transliteration = False):
    """
    Process audio files in a directory, perform transcription, and update a CSV file.

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
                    
                #continue with the files
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

