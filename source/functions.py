import os
import sys
import json

def load_json_file(file_path):
    """Utility function to load JSON files with error handling."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"Error: {file_path} not found.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Failed to parse JSON from {file_path}.")
        sys.exit(1)

def load_text_file(file_path):
    """Utility function to load text files with error handling."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read().splitlines()
    except FileNotFoundError:
        print(f"Error: {file_path} not found.")
        sys.exit(1)

def set_global_variables():
    """Loads necessary configurations and paths."""
    current_dir = os.getcwd()
    
    languages_path = os.path.join(current_dir, 'materials', 'LANGUAGES')
    columns_path = os.path.join(current_dir, 'materials', 'OBLIGATORY_COLUMNS')
    nolatin_path = os.path.join(current_dir, 'materials', 'NO_LATIN')
    leipzig_path = os.path.join(current_dir, 'materials', 'LEIPZIG_GLOSSARY')

    LANGUAGES = load_json_file(languages_path)
    OBLIGATORY_COLUMNS = load_text_file(columns_path)
    NO_LATIN = load_text_file(nolatin_path)
    LEIPZIG_GLOSSARY = load_json_file(leipzig_path)

    return LANGUAGES, NO_LATIN, OBLIGATORY_COLUMNS, LEIPZIG_GLOSSARY

def find_language(language, LANGUAGES):
    """Finds the language code by its name."""
    language_lower = language.lower()
    
    # Reverse the LANGUAGES dictionary for language name -> code lookup
    reversed_languages = {value.lower(): key for key, value in LANGUAGES.items()}
    
    language_code = reversed_languages.get(language_lower)
    
    if language_code:
        print(f'Language recognized: {language_code}')
        return language_code
    else:
        print(f"Unsupported language: {language}")
        sys.exit(1)

def clean_string(input_string):
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
