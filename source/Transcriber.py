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
import logging
import re
from functions import set_global_variables, find_language, clean_string, find_ffmpeg

LANGUAGES, NO_LATIN, OBLIGATORY_COLUMNS, _ = set_global_variables()

ffmpeg_path = find_ffmpeg()

warnings.filterwarnings("ignore")

# Configure logger globally
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create a StreamHandler for console output
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARNING)
console_handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(console_handler)


class Transcriber():
    def __init__(self, input_dir, language, device="cuda"):
        self.input_dir = input_dir
        self.language_code = find_language(language, LANGUAGES)
        self.model = whisper.load_model("large-v3", device=device)        
        

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
            filename_regexp = re.compile(r'blockNr_(?P<block>\d+)_taskNr_(?P<task>\d+)_trialNr_(?P<trial>\d+).*')
            for subdir, dirs, files in os.walk(self.input_dir):
                if 'binaries' in subdir:
                    logger.info(f"using device {self.model.device}")
                    logger.info(f"Processing {subdir}")
                    print(f"Processing {subdir}")
                    log_file_path = os.path.join(os.path.dirname(subdir), "transcription.log")
                    file_handler = logging.FileHandler(log_file_path)
                    file_handler.setLevel(logging.DEBUG)
                    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
                    logger.addHandler(file_handler)
                    logger.info(f"Logging to {log_file_path}")


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
                    files.sort()
                    for file in tqdm(files, desc=f"Transcribing"):
                        try: 
                            if file.endswith('.mp3') or file.endswith('.mp4') or file.endswith('.m4a'):
                                count += 1
                                logger.debug(f'processing file {count}/{len(files)} in {subdir}: {file}')
                                audio_file_path = os.path.abspath(os.path.join(subdir, file))
                                transcription = ""
                                transcription = self.model.transcribe(audio_file_path, language = self.language_code)
                                transcription = clean_string(transcription["text"])
                                if verbose:
                                    tqdm.write(transcription)
                                    
                                # search for the filename in the data frame
                                series = df[df.isin([file])].stack()
                                if len(series) == 0:
                                    # the filename cannot be found in the CSV -> insert it in the row identified by block, task and trial

                                    # extract blockNr, taskNr and trialNr from the filename
                                    filename_match = filename_regexp.search(file)
                                    if filename_match is None:
                                        logger.warning(f'   file {file} was not found in the CSV and does match block_task_trial pattern ... the transcription was not added to the CSV!')
                                    block_nr = int(filename_match.group('block'))
                                    task_nr = int(filename_match.group('task'))
                                    trial_nr = int(filename_match.group('trial'))

                                    # add the filename to the dataframe
                                    selection_condition = (df['Block_Nr'] == block_nr) & (df['Task_Nr'] == task_nr) & (df['Trial_Nr'] == trial_nr)
                                    if len(df.loc[selection_condition]) == 0:
                                        # we could not identify the corresponding row in the CSV so we don't know where to add the transcription
                                        logger.warning(f'   file {file} was not found in the CSV and there is no row for block {block_nr}, task {task_nr}, trial {trial_nr} ... the transcription was not added to the CSV!')
                                    else:
                                        # identify the first empty missing_filename_<number> cell in the row
                                        column_counter = 1
                                        missing_filename_column = f'missing_filename_{column_counter}'
                                        while (missing_filename_column in df.columns) and not df.loc[selection_condition, missing_filename_column].isna().all():
                                            column_counter += 1
                                            missing_filename_column = f'missing_filename_{column_counter}'
                                        df.loc[selection_condition,missing_filename_column] = file
                                        logger.debug(
                                            f"Type of df.loc[selection_condition, 'automatic_transcription']: "
                                            f"{type(df.loc[selection_condition, 'automatic_transcription'])}"
                                        )
                                        df.loc[selection_condition, 'automatic_transcription'] += f"{count}: {transcription} - "
                                        logger.info(f'    filename {file} was not found in the CSV but was added to the corresponding row')
                                else:
                                    for idx, value in series.items():
                                        if pd.isna(df.at[idx[0], "automatic_transcription"]):
                                            logger.debug(
                                                f"Row {idx[0]}: 'automatic_transcription' is NaN, initializing empty string.")
                                            df.at[idx[0], "automatic_transcription"] = ""
                                        else:
                                            logger.debug(
                                                f"Row {idx[0]}: 'automatic_transcription' is Type "
                                                f"{type(df.at[idx[0], 'automatic_transcription'])}"
                                            )
                                        df.at[idx[0], "automatic_transcription"] += f"{count}: {transcription} "
                        except Exception as e:
                            logger.error(f'problem with file {file}: {e}')
                            continue

                    df.to_excel(excel_output_file)
                    logger.info(f"\nTranscription and translation completed for {subdir}.")
                    logger.removeHandler(file_handler)
                    file_handler.close()
        except Exception as e:
            logger.error(f"An error occurred: {str(e)}")
            logger.removeHandler(file_handler)
            file_handler.close()


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

