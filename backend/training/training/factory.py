from training.training.SpacyTrainer import SpacyTrainer
class TrainerFactory:
    @staticmethod
    def get_trainer(action, language: str, study: str):
        if action == "gloss":
            if language in ["ca", "zh", "hr", "da", "nl", "en", "fi", "fr", "de", "el", "it", "ja", "ko",
                            "lt", "mk", "xx", "nb", "pl", "pt", "ro", "ru", "sl", "es", "sv", "uk", "af",
                            #No pretrained models for these languages
                            "sq", "am", "grc", "ar", "hy", "az", "eu", "bn", "bg", "cs", "et", "fo", "gu",
                            "he", "hi", "hu", "is", "id", "ga", "kn", "ky", "la", "lv", "lij", "dsb", "lg",
                            "lb", "ms", "ml", "mr", "ne", "nn", "fa", "sa", "sr", "tn", "si", "sk", "tl",
                            "ta", "tt", "te", "th", "ti", "tr", "hsb", "ur", "vi", "yo"
                            ]:
                return SpacyTrainer(language, study)
            else:
                raise ValueError(f"No trainer available for language: {language}")