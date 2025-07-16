from inference.processors.abstract import DataProcessor
from inference.processors.transcription import TranscriptionProcessor
from inference.processors.translation import TranslationProcessor
from inference.processors.glossing import GlossingProcessor
from inference.processors.transliteration import Transliterator
from inference.processors.ColumnCreation import ColumnCreationProcessor

class ProcessorFactory:
    @staticmethod
    def get_processor(language: str, action: str, instruction: str, translationModel = None, glossingModel = None) -> DataProcessor:
        if action == "transcribe":
            return TranscriptionProcessor(language, instruction)
        elif action == "translate":
            return TranslationProcessor(language, instruction, translationModel)
        elif action == "gloss":
            return GlossingProcessor(language, instruction, translationModel, glossingModel)
        elif action == "transliterate":
            return Transliterator(language, instruction)
        elif action == "create columns":
            return ColumnCreationProcessor(language, instruction)
        else:
            raise ValueError(f"No data processor available for action: {action}")