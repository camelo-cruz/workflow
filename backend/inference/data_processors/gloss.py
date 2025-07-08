import os
import sys
import shutil
import tempfile
import logging
import pandas as pd
from tqdm import tqdm
from utils.functions import find_language, format_excel_output, set_global_variables

from inference.glossing.abstract import GlossingStrategy
from inference.glossing.factory import GlossingStrategyFactory

LANGUAGES, NO_LATIN, OBLIGATORY_COLUMNS = set_global_variables() 

logger = logging.getLogger(__name__) 

class Glosser:
    def __init__(self, input_dir: str, language: str, instruction: str, glossingModel: str | None = None, translationModel: str | None = None):
        self.input_dir = input_dir
        self.language_code = find_language(language, LANGUAGES)
        self.instruction = instruction
        self.glossingModel = glossingModel
        self.translationModel = translationModel
        print(f"Initializing Glosser for language: {self.language_code}, instruction: {self.instruction}, glossingModel: {self.glossingModel}, translationModel: {self.translationModel}", flush=True)

        self._spacy_data_dir = tempfile.mkdtemp(prefix="spacy_data_")
        os.environ["SPACY_DATA"] = self._spacy_data_dir

        self.strategy: GlossingStrategy = GlossingStrategyFactory.get_strategy(self.language_code, glossingModel)

        try:
            shutil.rmtree(self._spacy_data_dir)
        except Exception as err:
            print(f"Warning: failed to delete spaCy cache: {err}", flush=True)

    def process_data(self):
        try:
            for subdir, dirs, files in os.walk(self.input_dir):
                for file in files:
                    if not file.endswith("annotated.xlsx"):
                        continue

                    excel_path = os.path.join(subdir, file)
                    df = pd.read_excel(excel_path)

                    if self.instruction == "sentences":
                        column_to_gloss = "latin_transcription_utterance_used"
                        if self.language_code in NO_LATIN:
                            column_to_gloss = "transcription_original_script_utterance_used"
                    elif self.instruction == "corrected":
                        column_to_gloss = "latin_transcription_everything"
                        if self.language_code in NO_LATIN:
                            column_to_gloss = "transcription_original_script"
                    elif self.instruction == "automatic":
                        column_to_gloss = "automatic_transcription"
                    else:
                        raise ValueError(f"Unsupported instruction: {self.instruction!r}")

                    if column_to_gloss not in df.columns:
                        print(f"No column '{column_to_gloss}' found in file: {file}")
                        continue

                    print(f"Glossing file: {excel_path} (column: {column_to_gloss!r})")
                    source_series = df[column_to_gloss]
                    glossed_utterances = []

                    for cell in tqdm(source_series, desc="Processing sentences", total=len(source_series)):
                        if isinstance(cell, str):
                            lines = cell.split("\n")
                            per_line = [self.strategy.gloss(line) for line in lines]
                            glossed_utterances.append("\n".join(per_line))
                        else:
                            glossed_utterances.append("")

                    df["automatic_glossing"] = glossed_utterances
                    df["glossing_utterance_used"] = glossed_utterances
                    df.to_excel(excel_path, index=False, engine="openpyxl")
                    format_excel_output(excel_path, ["glossing_utterance_used"])

        except Exception as e:
            logger.error(f"Problem with file {excel_path} occurred: {e}")