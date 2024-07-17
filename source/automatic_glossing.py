# -*- coding: utf-8 -*-
"""
Copyright (C) 2024  Alejandra Camelo Cruz

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

import re
import os
import sys
import spacy
import json
import argparse
import pandas as pd
from tqdm import tqdm
from spacy.cli import download
from transformers import MarianMTModel, MarianTokenizer

current_dir = os.getcwd()
language_path = os.path.join(current_dir, 'materials', 'LANGUAGES')
leipzig_path = os.path.join(current_dir, 'materials', 'LEIPZIG_GLOSSARY')

def load_json(path):
    """Utility function to load a JSON file."""
    try:
        with open(path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"Error: The file {path} does not exist.")
    except json.JSONDecodeError:
        print(f"Error: Failed to decode JSON from {path}")

LANGUAGES = load_json(language_path)
LEIPZIG_GLOSSARY = load_json(leipzig_path)
MODELS = {'de': {
            'translation': 'Helsinki-NLP/opus-mt-de-en', 
            'morphology': 'de_dep_news_trf', 
            'prompt': ['Gegeben den originalen Satz', 'der Wurzel des Wortes', 'im Kontext ist']},
          'ukr': {
              'translation': 'Helsinki-NLP/opus-mt-uk-en', 
              'morphology': 'uk_core_news_trf',
              'prompt': []}
          }

def load_models(language_code):
    """
    This function loads important models for the posterior workflow such us 
    the model for the morphological analysis, a tokenizer and an LLM to 
    perform contextual translation

    Parameters
    ----------
    language_code : Str
        Language to download the models.

    Returns
    -------
    nlp : spacy model
        spacy model for morphological analysis.
    tokenizer : marian tokenizer
        tokenizer for sentences.
    translation_model : MML
        model for translating sentences.

    """
    model_name = MODELS[language_code]['morphology']
    try:
        nlp = spacy.load(model_name)
    except OSError:
        print(f"Model {model_name} not found. Downloading...")
        download(model_name)
        nlp = spacy.load(model_name)
    
    translation_model_name = MODELS[language_code]['translation']
    tokenizer = MarianTokenizer.from_pretrained(translation_model_name)
    translation_model = MarianMTModel.from_pretrained(translation_model_name)

    return nlp, tokenizer, translation_model

def translate_lemma_with_context(language_code, sentence, lemma, tokenizer, model):
    """
    Given a language, a lemma, a sentence, a tokenizer and a model, this function
    provides a contextual translation of the lemma given the sentence. This is done
    for translating lemmas for the glossing task

    Parameters
    ----------
    language : str
        language to perform the translation from.
    lemma : str
        lemma to translate.
    sentence : str
        sentence where the lemma is located.
    tokenizer : marian tokenizer
        tokenizer.
    model : marian model
        LLM to perfom translation.

    Returns
    -------
    str
        translated lemma.

    """
    prompt = MODELS[language_code]['prompt']
    prompt = f'{prompt[0]} {sentence} {prompt[1]} {lemma} {prompt[2]} = {lemma}'
    inputs = tokenizer(prompt, return_tensors="pt", padding=True)
    translated_tokens = model.generate(**inputs)
    translated_sentence = tokenizer.decode(translated_tokens[0], skip_special_tokens=True)
    remove_prompt = r'^.*?='
    translated_lemma = re.sub(remove_prompt, '', translated_sentence)
    return translated_lemma.strip()

def gloss_with_spacy(language_code, nlp, tokenizer, model, sentence):
    """
    This function performs the morphological analysis of a sentence given 
    a spacy model, a tokenizer and a translation model. It takes a sentence 
    and performs the analysis. Each token in the analyzed sentence is cleaned.
    It ignores parenthesis and numbers, as it is part of the transcriptions.
    The final glossed sentence is produced in the following way:
        - Lemma, part of speech category and morphological analysis are separated
        - lemma is translated
        - part of speech and morphological analysis are mapped to the leipzig 
        glossing rules standard, given a hand made glossary
        - This inofmration is merged again and after a final cleaning ignoring 
        other special characters it is returned
    

    Parameters
    ----------
    nlp : spacy model
        spacy model to per.
    tokenizer : marian tokenizzer
        tokenizer.
    model : marian model
        model to perform lemma translation.
    sentence : str
        sentence to gloss.

    Returns
    -------
    str
        glossed sentence.

    """
    glossed_sentence = ''
    doc = nlp(sentence)
    for token in doc:
        # Skip tokens containing digits or square brackets
        if re.search(r'[\d\[\]]', token.text):
            glossed_sentence += token.text
        else:
            # Get the lemma, POS, and morphological features
            lemma = token.lemma_
            pos = token.pos_
            morph = token.morph.to_dict()
    
            # Translate the lemma with added context
            translated_lemma = translate_lemma_with_context(language_code, sentence, lemma, tokenizer, model)
    
            # Map POS and morphological features to Leipzig abbreviations
            pos = LEIPZIG_GLOSSARY.get(pos, pos)
            morph_tags = []
            for key, value in morph.items():
                morph_tags.append(LEIPZIG_GLOSSARY.get(f"{key}={value}", f"{key}={value}"))

            morph_str = ".".join(morph_tags)
            glossed_word = f'{translated_lemma}.{pos}.{morph_str}'
            
            # Final editing and cleaning
            glossed_word = re.sub(r'[| ]', '.', glossed_word)
            glossed_word = re.sub(r'\..*=', '.', glossed_word)
            
            glossed_sentence += glossed_word + ' '

    return glossed_sentence.strip()

def process_data(input_dir, language_code):
    """
    Process function which iterated over folders and finds already annotated data.
    The annotated excels are read and the information from the relevant column
    "latin_transcription_utterance_used" is taken and each sentence is analysed 
    morphologically.
    This produces a new excel file  glossed with the column automatic glossing
    containing the glossed sentences.

    Parameters
    ----------
    input_dir : str
        path to the parent dir containing the files to process.
    language_code : str
        code of the language to do the processing.

    Returns
    -------
    None.

    """
    nlp, tokenizer, model = load_models(language_code)
    try:
        for subdir, dirs, files in os.walk(input_dir):
            for file in files:
                if file.endswith('annotated.xlsx'):
                    excel_input_file = os.path.join(subdir, file)
                    df = pd.read_excel(excel_input_file)
                    if 'latin_transcription_utterance_used' in df.columns:
                        print('Glossing:', file)
                        excel_output_file = os.path.join(subdir, f'{os.path.splitext(file)[0]}_glossed.xlsx')
                        sentences_groups = df['latin_transcription_utterance_used']
                        glossed_utterances = []
                        for idx, sentences in enumerate(sentences_groups):
                            if isinstance(sentences, str):
                                sentences = sentences.split('\n')
                                glossed_sentences = []
                                for sentence in sentences:
                                    glossed = gloss_with_spacy(language_code, nlp, tokenizer, model, sentence)
                                    print(sentence)
                                    print(glossed)
                                    glossed_sentences.append(glossed)
                                glossed_utterances.append('\n'.join(glossed_sentences))
                            else:
                                glossed_utterances.append('')
                        df['automatic_glossing'] = glossed_utterances
                        df.to_excel(excel_output_file, index=False)
                    else:
                        print('No column to transcribe in file:', file)
    except Exception as e:
        print("Error processing data:", e)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Automatic glossing")
    parser.add_argument("input_dir", help="Main directory with files to gloss")
    parser.add_argument("language", help="Language to gloss")
    args = parser.parse_args()
    
    language_code = next((code for code, name in LANGUAGES.items() if name == args.language.lower()), None)
    if language_code:
        print(f"Glossing for {args.language} ({language_code})")
        process_data(args.input_dir, language_code)
    else:
        print(f"Unsupported language: {args.language}")
        sys.exit(1)

if __name__ == '__main__':
    main()