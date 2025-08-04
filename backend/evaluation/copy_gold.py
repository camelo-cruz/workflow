#!/usr/bin/env python3
import os
import re
import pandas as pd
import argparse

def process_file(file_path):
    df = pd.read_excel(file_path)

    # Only proceed if both columns exist
    if 'gold_glossing' in df.columns and 'glossing_utterance_used' in df.columns:
        # Copy and clean
        df['glossing_utterance_used'] = df['gold_glossing']

        # Save back to file
        df.to_excel(file_path, index=False)
        print(f"Updated column in: {file_path}")
    else:
        print(f"Required columns missing in {file_path}")

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
