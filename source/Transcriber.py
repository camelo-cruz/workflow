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
from functions import set_global_variables, find_language, clean_string, find_ffmpeg

LANGUAGES, NO_LATIN, OBLIGATORY_COLUMNS, _ = set_global_variables()

#ffmpeg_path = find_ffmpeg()
#os.environ["PATH"] += os.pathsep + os.path.dirname(ffmpeg_path)

warnings.filterwarnings("ignore")

# Load and initialize the Whisper model for audio processing
model = whisper.load_model("large-v3")

class Transcriber():
    def __init__(self, input_dir, language):
        self.input_dir = input_dir
        self.language_code = find_language(language, LANGUAGES)


    def process_data(self, verbose=False):
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
            
        Returns:
            None.
        """
        try:
            for subdir, dirs, files in os.walk(self.input_dir):
                if 'binaries' in subdir:
                    csv_file_path = os.path.join(subdir, '..', 'trials_and_sessions.csv')
                    excel_file_path = os.path.join(subdir, '..', 'trials_and_sessions.xlsx')
                    excel_output_file = os.path.join(subdir, '..', 'trials_and_sessions_annotated.xlsx')
                    if os.path.exists(csv_file_path):
                        df = pd.read_csv(csv_file_path)
                    elif os.path.exists(excel_file_path):
                        df = pd.read_excel(excel_file_path)
                    

                    for column in OBLIGATORY_COLUMNS:
                        if column not in df:
                            df[column] = ""
                    
                    if self.language_code not in NO_LATIN:
                        df = df.drop(columns=['transcription_original_script'])
                        df = df.drop(columns=['transcription_original_script_utterance_used'])
                        
                    count = 0
                    for file in tqdm(files, desc=f"Processing Files", unit="file"):
                        try: 
                            if file.endswith('.mp3'):
                                count += 1
                                audio_file_path = os.path.abspath(os.path.join(subdir, file))
                                transcription = ""
                                transcription = model.transcribe(audio_file_path, language = self.language_code)
                                transcription = clean_string(transcription["text"])
                                if verbose:
                                    print(transcription)

                                series = df[df.isin([file])].stack()
                                for idx, value in series.items():
                                    df.at[idx[0], "automatic_transcription"] += f"{count}: {transcription}"
                        except Exception as e:
                            print(f'problem with file {file}: {e}')
                            continue

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
    parser.add_argument("--verbose", action="store_true", help="Print full ouptput")
    args = parser.parse_args()

    transcriber = Transcriber(args.input_dir, args.language)
    transcriber.process_data(args.verbose)

if __name__ == "__main__":
    main()

