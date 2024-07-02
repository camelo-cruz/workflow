import os 
import pandas as pd
from deep_translator import GoogleTranslator
import argparse
import json

# Get the current directory
current_dir = os.getcwd()


# Construct the absolute path to the file
file_path = os.path.join(current_dir, 'materials', 'LANGUAGES.txt')

with open(file_path, 'r', encoding='utf-8') as file:
    LANGUAGES = json.load(file)

def translate(file, source_language):
    df = pd.read_excel(file)
    
    for i in range(len(df)):
        try:
            df.loc[i,"translation_everything"] = GoogleTranslator(source=source_language, target='en').translate(df["latin_transcription_everything"][i])
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
    parser.add_argument("source_language")
    args = parser.parse_args()
    
    language = None
    for code, name in LANGUAGES.items():
        if name == args.language.lower():
            language = code
    
    for subdir, dir, files in os.walk(args.input_dir):
        for file in files:
            if file.endswith('annotated.xlsx'):
                file = os.path.join(subdir, file)
                df = translate(file, language)
                df.to_excel(file)


if __name__ == "__main__":
    main()