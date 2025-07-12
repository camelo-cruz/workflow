import os
import pandas as pd
from tqdm import tqdm

from utils.functions import (
    find_language,
    set_global_variables,
    format_excel_output,
)
from inference.transliteration.abstract import TransliterationStrategy
from inference.transliteration.factory import TransliterationStrategyFactory

from inference.data_processors.abstract import DataProcessor  # wherever you put it

LANGUAGES, NO_LATIN, OBLIGATORY_COLUMNS = set_global_variables()


class Transliterator(DataProcessor):
    """
    Processes all '*.annotated.xlsx' files in a directory,
    applying a TransliterationStrategy to each DataFrame.
    """

    def __init__(self, language: str, instruction: str, device: str = "cpu"):
        # initialize base with language & instruction
        super().__init__(language, instruction)
        self.device = device
        # pick strategy based on resolved language code
        self.strategy: TransliterationStrategy = TransliterationStrategyFactory.get_strategy(
            self.language
        )

    def _process_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        # determine source/target columns by instruction
        if self.instruction == "sentences":
            source = "transcription_original_script_utterance_used"
            target = "latin_transcription_utterance_used"
        elif self.instruction == "corrected":
            source = "transcription_original_script"
            target = "latin_transcription_everything"
        else:
            raise ValueError(f"Unsupported instruction: {self.instruction}")

        # ensure target column exists
        df[target] = df.get(target, "").astype(object)

        # transliterate every non-null source sentence
        for sentence in tqdm(
            df[source].dropna(), desc="Transliterating sentences", leave=False
        ):
            # find all rows where this sentence occurs
            hits = df[df[source] == sentence].index
            for idx in hits:
                # initialize cell if empty
                if pd.isna(df.at[idx, target]) or df.at[idx, target] == "":
                    df.at[idx, target] = ""
                # apply strategy and append if new
                translit = self.strategy.transliterate(sentence)
                if translit not in df.at[idx, target]:
                    df.at[idx, target] += translit + " "
        return df

    def _write_file(self, path: str, df: pd.DataFrame):
        # write DataFrame back to the same Excel file
        df.to_excel(path, index=False)
        # apply any post‐formatting (e.g. column widths, styles)
        # note: for 'corrected' instruction, we target 'latin_transcription_everything'
        target_col = (
            "latin_transcription_utterance_used"
            if self.instruction == "sentences"
            else "latin_transcription_everything"
        )
        format_excel_output(path, target_col)