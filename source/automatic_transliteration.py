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
import json
import romkan
import pykakasi
import argparse
import spacy
import pandas as pd
from tqdm import tqdm
from transliterate import translit


current_dir = os.getcwd()

nolatin_path = os.path.abspath(os.path.join(current_dir, 'materials', 'NO_LATIN'))
languages_path = os.path.abspath(os.path.join(current_dir, 'materials', 'LANGUAGES'))

with open(nolatin_path, 'r', encoding='utf-8') as file:
    NO_LATIN = file.read().splitlines()

with open(languages_path, 'r', encoding='utf-8') as file:
    LANGUAGES = json.load(file)

def kanji_hiragana_katakana_to_romaji(sentence):
    """
    Convert a Japanese sentence (with Kanji, Hiragana, Katakana) to Romaji.
    
    Parameters:
    -----------
    sentence : str
        Japanese sentence to convert to Romaji.
    
    Returns:
    --------
    romaji_sentence : str
        The sentence converted into Romaji.
    """
    '''
    nlp = spacy.load('ja_core_news_trf')
    doc = nlp(sentence)
    
    # Convert Kanji to Kana (Hiragana/Katakana) and Kana to Romaji
    romaji_sentence = ''
    for word in doc:
        morph = word.morph.to_dict()

        # Check if the word contains Latin alphabet characters
        if word.text.isascii():  # Latin alphabet check
            romaji_word = word.text  # Leave the word unchanged if it's in Latin alphabet
        elif word.text == "、":  # Japanese comma
            romaji_word = ","  # Convert to a Latin comma
        elif word.text == "。":  # Japanese period
            romaji_word = "."  # Convert to a Latin period
        else:
            kana_form = morph['Reading'] if 'Reading' in morph else str(word)
            
            # Convert the Kana form to Romaji using romkan
            romaji_word = romkan.to_roma(kana_form)
        
        # Append the Romaji word to the sentence
        romaji_sentence += romaji_word + ' '
    '''

    romaji_sentence = ''
    kks = pykakasi.kakasi()
    result = kks.convert(sentence)
    for item in result:
        element = item['hepburn']
        romaji_sentence += f'{element} '

    
    return romaji_sentence.strip()

def transliterate(file, instruction, language_code):
    """
    Transliterate sentences based on the language_code and instruction.
    
    Parameters:
    -----------
    file : str
        Path to the file to process.
    instruction : str
        Type of processing ("sentences", "corrected_transcription").
    language_code : str
        Source language code for transliteration.
    
    Returns:
    --------
    df : pandas.DataFrame
        Dataframe with transliterated sentences.
    """
    df = pd.read_excel(file)
    
    # Choose source and target columns based on the instruction
    if instruction == 'sentences':
        source = 'transcription_original_script_utterance_used'
        target = 'latin_transcription_utterance_used'
    elif instruction == 'corrected_transcription':
        source = 'transcription_original_script'
        target = 'latin_transcription_everything'
    
    # Ensure target column exists in the dataframe
    if target not in df.columns:
        df[target] = ""
    else:
        df[target] = ""

    df[target] = df[target].astype('object')
    
    for sentence in df[source].dropna():  # Handle missing values in the source column
        series = df[df.isin([sentence])].stack()
        for idx, value in series.items():
            if pd.isna(df.at[idx[0], target]):
                df.at[idx[0], target] = ""

            if language_code == "ru":
                df.at[idx[0], target] += f"{translit(sentence, 'ru', reversed=True)} "
            elif language_code == "uk":
                df.at[idx[0], target] += f"{translit(sentence, 'uk', reversed=True)} "
            elif language_code == "ja":
                df.at[idx[0], target] += f"{kanji_hiragana_katakana_to_romaji(sentence)} "

    return df

def main():
    """
    Main function to transliterate a manually prepared transcription.
    
    Parameters:
    -----------
    input_dir : str
        Directory containing files to transliterate.
    instruction : str
        Type of processing ("automatic_transcription", "corrected_transcription", "sentences").
    source_language : str
        Source language to transliterate from.
    """
    parser = argparse.ArgumentParser(description="Automatic transcription")
    parser.add_argument("input_dir", help="Directory with files to transliterate.")
    parser.add_argument("instruction", choices=[ "corrected_transcription", "sentences"], 
                        help="Type of instruction for processing.")
    parser.add_argument("source_language", help="Source language for transliteration.")
    args = parser.parse_args()

    # Find the language code based on the input language
    language = None
    for code, name in LANGUAGES.items():
        if name == args.source_language.lower():
            language = code
            print(f'transliterating for {language}')
    
    if not language:
        print(f"Error: Unsupported language '{args.source_language}'.")
        return
    
    # Process files in the input directory
    to_process = []
    for subdir, dirs, files in os.walk(args.input_dir):
        for file in files:
            if file.endswith('annotated.xlsx'):
                to_process.append(os.path.join(subdir, file))

    for file_path in tqdm(to_process, desc=f"Processing Files", unit="file"):
        df = transliterate(file_path, args.instruction, language)
        df.to_excel(file_path, index=False)

if __name__ == "__main__":
    main()
