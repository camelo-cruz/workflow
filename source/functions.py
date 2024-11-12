import os
import sys
import json
import string
import os
import shutil
import subprocess
import urllib.request
import zipfile


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


def install_ffmpeg():
    destination_path = os.path.expanduser("~")
    ffmpeg_url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

    zip_path = os.path.join(destination_path, "ffmpeg-7.1-essentials_build.zip")
    ffmpeg_extract_path = os.path.join(destination_path, "ffmpeg")

    try:
        print("Downloading ffmpeg...")
        urllib.request.urlretrieve(ffmpeg_url, zip_path)
        print("Download complete.")

        print(f"Extracting ffmpeg to {ffmpeg_extract_path}...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(ffmpeg_extract_path)
        print("Extraction complete.")

        os.remove(zip_path)

        print(f"ffmpeg has been installed to {ffmpeg_extract_path}.")
        print("Adding path to system's PATH environment variable.")
        ffmpeg_path = os.path.join(ffmpeg_extract_path, "ffmpeg-7.1-essentials_build/bin/ffmpeg.exe")
        os.environ["PATH"] += os.pathsep + os.path.dirname(ffmpeg_path)
        return ffmpeg_path
    except Exception as e:
        print("An error occurred:", e)


def find_ffmpeg():
    """Dynamically finds ffmpeg executable path"""
    ffmpeg_path = shutil.which("ffmpeg")

    if not ffmpeg_path:
        print("FFmpeg not found. Attempting to install FFmpeg...")

        ffmpeg_path = install_ffmpeg()
    else:
        return ffmpeg_path

    if os.path.exists(ffmpeg_path):
        return ffmpeg_path
    else:
        raise FileNotFoundError("FFmpeg installation failed. "
                                "Please install it manually.")
