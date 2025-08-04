#!/usr/bin/env python3
"""
Script to find all "trials_and_sessions_annotated.xlsx" files in subfolders and perform the following replacements in every cell:
 1. Replace any backslash (`\`) with a dash (`-`).
 2. Replace any dot before an uppercase word portion (e.g. ".ABC") with a dash (e.g. "-ABC").
 3. Replace any dash between lowercase letter sequences (e.g. "abc-def") with a dot (e.g. "abc.def").

Usage:
    python process_annotated_files.py /path/to/root_directory

If no path is given, the current directory is used.
"""
import os
import re
import pandas as pd
import argparse

def process_value(value):
    if not isinstance(value, str):
        return value
    
    # 1. Remove things like (1), [note], etc.
    value = re.sub(r'[\(\[][^\]\)\(\[]*[\)\]]', '', value)

    # 3. Replace dot before uppercase/digit with dash
    value = re.sub(r'\.(?=[A-Z0-9])', '-', value)

    # 4. Replace lowercase-lowercase dashes with dots
    value = re.sub(r'(?<=[a-z])-(?=[a-z])', '.', value)

    value = re.sub(r'\s+', ' ', value)
    return value.strip()

def process_file(file_path):
    df = pd.read_excel(file_path, dtype=str)
    if df.astype(str).apply(lambda col: col.str.contains(r'\b(REL|LOC)-(cat|up)')).any().any():
        print(f"Match found in: {file_path}")

def main(root_dir):
    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            # Match exactly "trials_and_sessions_annotated.xlsx" (case-insensitive)
            if fname.lower() == 'trials_and_sessions_annotated.xlsx':
                full_path = os.path.join(dirpath, fname)
                try:
                    process_file(full_path)
                except Exception as e:
                    print(f"Error processing {full_path}: {e}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Find and update all trials_and_sessions_annotated.xlsx files in subfolders'
    )
    parser.add_argument(
        'root_dir', nargs='?', default='.',
        help='Root directory to start searching (default: current directory)'
    )
    args = parser.parse_args()
    main(args.root_dir)
