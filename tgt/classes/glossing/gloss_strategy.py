class GlossStrategy:
    def __init__(self, language_code: str):
        self.language_code = language_code

    def load_model(self):
        raise NotImplementedError

    def gloss_sentence(self, sentence: str) -> str:
        raise NotImplementedError
