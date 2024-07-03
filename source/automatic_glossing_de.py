#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Jun 12 18:40:45 2024

@author: alejandra
"""

import re
import os
import sys
import spacy
import json
import argparse
import pandas as pd
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
    

MODEL_TRANSLATION = {'de': 'Helsinki-NLP/opus-mt-de-en'}

def load_models(language_code):
    nlp = spacy.load(f"{language_code}_dep_news_trf")
    model_name = MODEL_TRANSLATION[language_code]
    tokenizer = MarianTokenizer.from_pretrained(model_name)
    translation_model = MarianMTModel.from_pretrained(model_name)
    return nlp, tokenizer, translation_model

def translate_lemma_with_context(language, lemma, sentence, tokenizer, model):
    prompt = f'Gegeben den originalen Satz "{sentence}", der Wurzel des Wortes "{lemma}" im Kontext ist = {lemma}'
    inputs = tokenizer(prompt, return_tensors="pt", padding=True)
    translated_tokens = model.generate(**inputs)
    translated_sentence = tokenizer.decode(translated_tokens[0], skip_special_tokens=True)
    remove_prompt = r'^.*?='
    translated_lemma = re.sub(remove_prompt, '', translated_sentence)
    return translated_lemma.strip()

def gloss_with_spacy(nlp, tokenizer, model, sentence):
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
            translated_lemma = translate_lemma_with_context('de', lemma, sentence, tokenizer, model)
    
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
    nlp, tokenizer, model = load_models(language_code)
    try:
        for subdir, dirs, files in os.walk(input_dir):
            for file in files:
                if file.endswith('.xlsx'):
                    excel_input_file = os.path.join(subdir, file)
                    df = pd.read_excel(excel_input_file)
                    if 'glossing_object_language' in df.columns:
                        print('Glossing:', file)
                        excel_output_file = os.path.join(subdir, f'{os.path.splitext(file)[0]}_glossed.xlsx')
                        sentences_groups = df['glossing_object_language']
                        glossed_utterances = []
                        for idx, sentences in enumerate(sentences_groups):
                            if isinstance(sentences, str):
                                sentences = sentences.split('\n')
                                glossed_sentences = []
                                for sentence in sentences:
                                    glossed = gloss_with_spacy(nlp, tokenizer, model, sentence)
                                    glossed_sentences.append(glossed)
                                glossed_utterances.append('\n'.join(glossed_sentences))
                            else:
                                glossed_utterances.append('')
                        df['glossing_utterance_used'] = glossed_utterances
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
        print(f"Transcribing for {args.language} ({language_code})")
        process_data(args.input_dir, language_code)
    else:
        print(f"Unsupported language: {args.language}")
        sys.exit(1)

if __name__ == '__main__':
    main()