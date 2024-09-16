import os
import json

def set_global_variables():
    # Store the current working directory for relative path calculations
    current_dir = os.getcwd()
    
    # Compute the absolute file path for the language configurations
    languages_path = os.path.abspath(os.path.join(current_dir, 'materials', 'LANGUAGES'))
    columns_path = os.path.abspath(os.path.join(current_dir, 'materials', 'OBLIGATORY_COLUMNS'))
    nolatin_path = os.path.abspath(os.path.join(current_dir, 'materials', 'NO_LATIN'))
    leipzig_path = os.path.join(current_dir, 'materials', 'LEIPZIG_GLOSSARY')

    # Load language configurations from a JSON file
    with open(languages_path, 'r', encoding='utf-8') as file:
        LANGUAGES = json.load(file)
        
    with open(columns_path, 'r', encoding='utf-8') as file:
        OBLIGATORY_COLUMNS = file.read().splitlines()

    with open(nolatin_path, 'r', encoding='utf-8') as file:
        NO_LATIN = file.read().splitlines()

    with open(leipzig_path, 'r', encoding='utf-8') as file:
        LEIPZIG_GLOSSARY = json.load(file)

    # Return the loaded configurations
    return LANGUAGES, NO_LATIN, OBLIGATORY_COLUMNS, LEIPZIG_GLOSSARY


