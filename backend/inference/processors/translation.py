import warnings
import pandas as pd
from tqdm import tqdm

from inference.translation.factory import TranslationStrategyFactory
from inference.translation.abstract import TranslationStrategy
from utils.functions import (
    set_global_variables,
    find_ffmpeg,
)
from inference.processors.abstract import DataProcessor  # adjust import path as needed

# Global setup
LANGUAGES, NO_LATIN, OBLIGATORY_COLUMNS = set_global_variables()
warnings.filterwarnings("ignore")
ffmpeg_path = find_ffmpeg()


class TranslationProcessor(DataProcessor):
    """
    Processes annotated Excel files by translating text in specified columns.
    """

    def __init__(
        self,
        language: str,
        instruction: str,
        device: str = "cpu",
    ):
        super().__init__(language, instruction)
        self.device = device
        self.strategy: TranslationStrategy = TranslationStrategyFactory.get_strategy(self.language)
        self.columns_to_highlight = {
            "automatic": "automatic_translation_automatic_transcription",
            "corrected": "translation_everything",
            "sentences": "translation_utterance_used",
        }.get(self.instruction)

    def _process_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        # Determine source and target columns
        auto_col = "automatic_transcription"
        corr_col = "latin_transcription_everything"
        sent_col = "latin_transcription_utterance_used"
        if self.language in NO_LATIN:
            corr_col = "transcription_original_script"
            sent_col = "transcription_original_script_utterance_used"

        source_col = {
            "corrected": corr_col,
            "automatic": auto_col,
            "sentences": sent_col,
        }.get(self.instruction, sent_col)

        cols_map = {
            "corrected": ["automatic_translation_corrected_transcription", "translation_everything"],
            "automatic": ["automatic_translation_automatic_transcription"],
            "sentences": ["automatic_translation_utterance_used", "translation_utterance_used"],
        }

        for idx, row in tqdm(df.iterrows(), desc="Translating rows"):
            if idx >= 100:
                self.logger.info(f"Reached max rows at {idx}")
                break
            text = row.get(source_col)
            if pd.isna(text) or not str(text).strip():
                continue
            try:
                translation = self.strategy.translate(str(text))
                if not translation:
                    continue
                for target_col in cols_map[self.instruction]:
                    df.at[idx, target_col] = translation
            except Exception as e:
                self.logger.error(f"Row {idx} translation error: {e}")
        return df