from inference.data_processors.abstract import DataProcessor
from inference.data_processors.transcription import TranscriptionProcessor
from inference.data_processors.translation import TranslationProcessor
from inference.data_processors.glossing import GlossingProcessor
from inference.data_processors.transliteration import Transliterator
from inference.data_processors.ColumnCreation import ColumnCreationProcessor

class ProcessorFactory:
    @staticmethod
    def get_processor(language: str, action: str, instruction: str, glossingModel = None, translationModel = None) -> DataProcessor:
        if action == "transcribe":
            return TranscriptionProcessor(language, instruction)
        elif action == "translate":
            return TranslationProcessor(language, instruction, translationModel)
        elif action == "gloss":
            return GlossingProcessor(language, instruction, glossingModel, translationModel)
        elif action == "transliterate":
            return Transliterator(language, instruction)
        elif action == "create columns":
            return ColumnCreationProcessor(language, instruction)
        else:
            raise ValueError(f"No data processor available for action: {action}")