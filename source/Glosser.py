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
import argparse
import pandas as pd
from tqdm import tqdm
from spacy.cli import download
from deep_translator import GoogleTranslator
from functions import set_global_variables, find_language

LANGUAGES, NO_LATIN, OBLIGATORY_COLUMNS, LEIPZIG_GLOSSARY = set_global_variables()

class Glosser():
    def __init__(self, input_dir, language):
        self.input_dir = input_dir
        self.language_code = find_language(language, LANGUAGES)
        self.load_models()

    def load_models(self):
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

        models = {'de':'de_dep_news_trf',
          'ukr': 'uk_core_news_trf',
          'pt': 'pt_core_news_lg',
          'ja': 'ja_core_news_trf'
          }
        
        model_name = models[self.language_code]
        try:
            self.nlp = spacy.load(model_name)
        except OSError:
            print(f"Model {model_name} not found. Downloading...")
            download(model_name)
            self.nlp = spacy.load(model_name)

    def gloss_japanese_with_spacy(self, sentence):     
        glossed_sentence = ''
        doc = self.nlp(sentence)
        
        # Iterating over each token in the sentence
        for token in doc:
            if token.pos_ != 'PUNCT':
                glossed_sentence += f"{token.text}.{token.pos_}.{token.dep_} "

        return glossed_sentence
    
    @staticmethod
    def clean_portuguese_sentence(glossed_sentence, lemmatized_sentence):
        glossed_sentence = glossed_sentence.split()
        lemmatized_words = lemmatized_sentence.split()

        wh_questions = ['que', 'qual', 'quem', 'quando', 'onde']

        for wh in wh_questions:
            if wh in lemmatized_words:
                wh_index = lemmatized_words.index(wh)
                # Ensure wh_index + 1 is within the bounds
                if wh_index + 1 < len(lemmatized_words) and lemmatized_words[wh_index + 1] == 'que':
                    glossed_sentence[wh_index + 1] = 'COMP'

                if wh == "quem" or wh == "que"and wh_index < len(glossed_sentence) and wh_index in [0, 1]:
                    glossed_sentence[wh_index] = glossed_sentence[wh_index].replace('F', '').replace('M', '')
                    glossed_sentence[wh_index] = glossed_sentence[wh_index].replace('SG', '').replace("PL", "")
                    glossed_sentence[wh_index] = glossed_sentence[wh_index].replace('REL', 'INT')

        if 'o que' in lemmatized_sentence:
            if 'o' in lemmatized_words:
                o_index = lemmatized_words.index('o')
                # Ensure o_index + 1 is within the bounds
                if o_index + 1 < len(lemmatized_words) and lemmatized_words[o_index + 1] == 'que':
                    del glossed_sentence[o_index]
        
        glossed_sentence = ' '.join(glossed_sentence)
        glossed_sentence = re.sub(r'\s+', ' ', glossed_sentence)
        glossed_sentence = re.sub(r'\. +', '. ', glossed_sentence)

        return glossed_sentence

    def gloss_with_spacy(self, sentence, verbose = False):
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
        lemmatized_sentence = ''
        doc = self.nlp(sentence)
        for token in doc:
            # Skip tokens containing digits or square brackets
            if re.search(r'\[|\d|\]', token.text):
                glossed_sentence += token.text
            else:
                # Get the lemma, POS, and morphological features
                lemma = token.lemma_
                morph = token.morph.to_dict()

                translated_lemma =  GoogleTranslator(source=self.language_code, target='en').translate(lemma)
                if isinstance(translated_lemma, str) and not lemma.isdigit():
                    translated_lemma = translated_lemma.lower()
                    translated_lemma = translated_lemma.replace(' ', '-')

                arttype = LEIPZIG_GLOSSARY.get(morph.get('PronType'), morph.get('PronType'))
                definite = LEIPZIG_GLOSSARY.get(morph.get('Definite'), morph.get('Definite'))
                person = LEIPZIG_GLOSSARY.get(morph.get('Person'), morph.get('Person'))
                number = LEIPZIG_GLOSSARY.get(morph.get('Number'), morph.get('Number'))
                gender = LEIPZIG_GLOSSARY.get(morph.get('Gender'), morph.get('Gender'))
                case = LEIPZIG_GLOSSARY.get(morph.get('Case'), morph.get('Case'))
                tense = LEIPZIG_GLOSSARY.get(morph.get('Tense'), morph.get('Tense'))
                mood = LEIPZIG_GLOSSARY.get(morph.get('Mood'), morph.get('Mood'))

                glossed_word = f"{translated_lemma}.{arttype}.{definite}.{gender}.{person}.{number}.{case}.{tense}.{mood}"
                #further cleaning
                glossed_word = re.sub(r'(?:\.|-|\b)None', '', glossed_word)
                glossed_word = re.sub(r'\b(the|a)\.', '', glossed_word)
                glossed_word = re.sub(r'--', '', glossed_word)
                glossed_word = re.sub(r'\b[h]e\.', 'M.3.', glossed_word)
                glossed_word = re.sub(r'\b[s]he\.', 'F.3.', glossed_word)
                
                glossed_sentence += glossed_word + ' '
                glossed_sentence.strip()
                lemmatized_sentence += lemma + ' '
                lemmatized_sentence.strip()

        if self.language_code == 'pt':
            glossed_sentence = self.clean_portuguese_sentence(glossed_sentence, lemmatized_sentence)

        if verbose:      
            print(glossed_sentence)
        return glossed_sentence

    def process_data(self):

        """
        Processes files in a directory to gloss sentences and saves the results.

        Parameters
        ----------
        input_dir : str
            Path to the parent directory containing files to process.
        language_code : str
            Language code for processing.

        Returns
        -------
        None.
        """
        try:
            for subdir, dirs, files in os.walk(self.input_dir):
                for file in files:
                    if file.endswith('annotated.xlsx'):
                        excel_file = os.path.join(subdir, file)
                        df = pd.read_excel(excel_file)
                        column_to_gloss = 'latin_transcription_utterance_used'
                        if self.language_code in NO_LATIN:
                            column_to_gloss = 'transcription_original_script_utterance_used'
                        if column_to_gloss in df.columns:
                            print('Glossing:', file)
                            sentences_groups = df[column_to_gloss]
                            glossed_utterances = []
                            
                            for idx, sentences in tqdm(enumerate(sentences_groups), desc='Processing sentences', total=len(sentences_groups)):
                                if isinstance(sentences, str):
                                    sentences = sentences.split('\n')
                                    glossed_sentences = []
                                    
                                    # Process each sentence with tqdm
                                    for sentence in sentences:
                                        if self.language_code == 'ja':
                                            glossed = self.gloss_japanese_with_spacy(self.nlp, sentence)
                                        else:
                                            glossed = self.gloss_with_spacy(sentence)
                                        glossed_sentences.append(glossed)
                                    glossed_utterances.append('\n'.join(glossed_sentences))
                                else:
                                    glossed_utterances.append('')
                            
                            df['automatic_glossing'] = glossed_utterances
                            df.to_excel(excel_file, index=False, engine='openpyxl')
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
    
    glosser = Glosser(args.input_dir, args.language)
    glosser.process_data()

if __name__ == '__main__':
    main()
