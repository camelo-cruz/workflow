import pandas as pd
from tqdm import tqdm

from utils.functions import (
    set_global_variables,
)
from inference.glossing.factory import GlossingStrategyFactory
from inference.glossing.abstract import GlossingStrategy
from inference.translation.factory import TranslationStrategyFactory

from inference.processors.abstract import DataProcessor

LANGUAGES, NO_LATIN, OBLIGATORY_COLUMNS = set_global_variables()


class GlossingProcessor(DataProcessor):
    """
    Concrete DataProcessor that applies a GlossingStrategy
    to each '*.annotated.xlsx' file under input_dir.
    """

    def __init__(
        self,
        language: str,
        instruction: str,
        glossing_model: str | None = None,
        translation_model: str | None = None,
    ):
        super().__init__(language=language, instruction=instruction)
        self.glossing_model = glossing_model
        self.translation_model = translation_model

        self.strategy: GlossingStrategy = GlossingStrategyFactory.get_strategy(
            self.language, self.glossing_model
        )
        try: 
            self.TranslationStrategy = TranslationStrategyFactory.get_strategy(
                self.language, self.translation_model
            )
        except Exception as e:
            self.logger.error(f"Error initializing translation strategy: {e}")
        
        self.columns_to_highlight = ["glossing_utterance_used"]

    def _process_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        # decide which column to gloss
        if self.instruction == "sentences":
            col = "latin_transcription_utterance_used"
            if self.language in NO_LATIN:
                col = "transcription_original_script_utterance_used"
        elif self.instruction == "corrected":
            col = "latin_transcription_everything"
            if self.language in NO_LATIN:
                col = "transcription_original_script"
        elif self.instruction == "automatic":
            col = "automatic_transcription"
        else:
            raise ValueError(f"Unsupported instruction: {self.instruction!r}")

        if col not in df.columns:
            return df

        glossed = []
        for cell in tqdm(df[col], desc="Glossing rows", total=len(df)):
            if isinstance(cell, str):
                lines = cell.split("\n")
                glossed.append("\n".join(self.strategy.gloss(line) for line in lines))
            else:
                glossed.append("")

        # attach results
        df["automatic_glossing"] = glossed
        df["glossing_utterance_used"] = glossed
        return df