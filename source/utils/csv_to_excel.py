# -*- coding: utf-8 -*-
"""
Created on Tue Jan  9 18:59:32 2024

@author: camelo.cruz
"""

import os
import argparse
import pandas as pd

def convert_csv_to_excel(csv_file_path):
    # Read CSV file into a pandas DataFrame
    df = pd.read_csv(csv_file_path)

    # Extract the base file name without the extension
    base_name = os.path.splitext(os.path.basename(csv_file_path))[0]

    # Create Excel file path by replacing the extension
    excel_file_path = os.path.join(os.path.dirname(csv_file_path), f"{base_name}.xlsx")

    # Write DataFrame to Excel file
    df.to_excel(excel_file_path, index=False)
    print(f"Converted {csv_file_path} to {excel_file_path}")

def main():
    
    parser = argparse.ArgumentParser(description = "automatic transcription")

    parser.add_argument("input_dir")

    args = parser.parse_args()

    directory = args.input_dir
    
    for subdir, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".csv"):
                csv_file_path = os.path.join(subdir, file)
                convert_csv_to_excel(csv_file_path)
                

if __name__ == "__main__":
    main()
                