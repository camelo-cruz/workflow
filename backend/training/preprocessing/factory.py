from training.preprocessing.UD import UDPreprocessor
class PreProcessorFactory:
    @staticmethod
    def get_preprocessor(action, language: str, study: str):
        if action == "gloss":
            return UDPreprocessor(language, study)