import os
import pandas as pd
from tqdm import tqdm
from utils.functions import find_language, format_excel_output, set_global_variables


from ..transliteration.abstract import TransliterationStrategy
from ..transliteration.factory import 

LANGUAGES, NO_LATIN, OBLIGATORY_COLUMNS = set_global_variables() 

class Transliterator:
    """
    Main class to process Excel files and apply transliteration.

    Attributes:
        input_dir: Directory containing files to process
        instruction: Type of processing ('sentences' or 'corrected')
        device: Unused here but kept for consistency
        language_code: Determined by find_language()
        strategy: Concrete TransliterationStrategy instance
    """

    def __init__(self, input_dir: str, language: str, instruction: str, device: str = 'cpu'):
        self.input_dir = input_dir
        self.instruction = instruction
        self.device = device
        self.language_code = find_language(language, LANGUAGES)
        self.strategy: TransliterationStrategy = TransliterationStrategyFactory.get_strategy(self.language_code)

    def transliterate_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply transliteration to the DataFrame and return it."""
        if self.instruction == 'sentences':
            source = 'transcription_original_script_utterance_used'
            target = 'latin_transcription_utterance_used'
        elif self.instruction == 'corrected':
            source = 'transcription_original_script'
            target = 'latin_transcription_everything'
        else:
            raise ValueError(f"Unsupported instruction: {self.instruction}")

        # Initialize or clear target column
        df[target] = df.get(target, "").astype(object)

        # Iterate through non-null sentences
        for sentence in df[source].dropna():
            series = df[df.isin([sentence])].stack()
            for idx, _ in series.items():
                if pd.isna(df.at[idx[0], target]):
                    df.at[idx[0], target] = ""
                transliterated = self.strategy.transliterate(sentence)
                if transliterated not in df.at[idx[0], target]:
                    df.at[idx[0], target] += f"{transliterated} "
        return df

    def process_data(self):
        """Walk input_dir, transliterate each annotated.xlsx file, and save results."""
        files_to_process = []
        for subdir, _, files in os.walk(self.input_dir):
            for file in files:
                if file.endswith('annotated.xlsx'):
                    files_to_process.append(os.path.join(subdir, file))

        for file_path in tqdm(files_to_process, desc="Processing Files", unit="file"):
            print(f"Processing {file_path}...")
            df = pd.read_excel(file_path)
            df = self.transliterate_df(df)
            df.to_excel(file_path, index=False)
            format_excel_output(file_path, 'latin_transcription_everything')
