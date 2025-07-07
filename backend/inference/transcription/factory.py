from inference.transcription.abstract import TranscriptionStrategy
from inference.transcription.whisperx import WhisperxStrategy
from inference.transcription.whisper import WhisperStrategy



class TranscriptionStrategyFactory:
    @staticmethod
    def get_strategy(language_code: str) -> TranscriptionStrategy:
        if language_code in ['en', 'fr', 'de', 'es', 'it', 'ja', 'nl', 'uk', 'pt', 'cs',
                             'ru', 'pl', 'hu', 'fi', 'fa', 'el', 'tr', 'da', 'he', 'vi', 'ko',
                             'ur', 'te', 'hi', 'ca', 'ml', 'no', 'nn', 'sk', 'sl', 'hr', 'ro',
                             'eu', 'gl', 'ka', 'lv', 'tl', 'zh']:
            return WhisperxStrategy(language_code)
        elif language_code in ['ar']:
            return WhisperStrategy(language_code)
