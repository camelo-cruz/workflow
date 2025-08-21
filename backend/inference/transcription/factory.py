from inference.transcription.abstract import TranscriptionStrategy
from inference.transcription.whisperx import WhisperxStrategy
from inference.transcription.whisper import WhisperStrategy
from inference.transcription.bengali import BengaliStrategy



class TranscriptionStrategyFactory:
    @staticmethod
    def get_strategy(language_code: str) -> TranscriptionStrategy:
        if language_code in ['en', 'fr', 'de', 'es', 'it', 'nl', 'uk', 'pt', 'cs',
                             'ru', 'pl', 'hu', 'fi', 'fa', 'el', 'tr', 'da', 'he', 'vi', 'ko',
                             'ur', 'te', 'hi', 'ca', 'ml', 'no', 'nn', 'sk', 'sl', 'hr', 'ro',
                             'eu', 'gl', 'ka', 'lv', 'tl', 'zh']:
            return WhisperxStrategy(language_code)
        elif language_code in ['ar', 'et', 'ja']:
            return WhisperStrategy(language_code)
        elif language_code in ['bn']:
            return BengaliStrategy(language_code)
        else:
            raise ValueError(f"No transcription strategy available for language code: {language_code}")
