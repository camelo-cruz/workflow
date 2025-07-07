from inference.pii_identifier.spacy_ner import SpacyIdentifier
from inference.pii_identifier.stanza_ner import StanzaIdentifier
from inference.pii_identifier.abstract import PIIStrategy

class PIIIdentifierFactory:
    @staticmethod
    def get_strategy(language_code: str, translationModel: str = None) -> PIIStrategy:
        if language_code in ['de', 'en', 'fr', 'zh', 'el', 'it', 'ja', 'pt', 'ro', 'ru', 'uk']:
            # Use spaCy for these languages
            return SpacyIdentifier(language_code)
        elif language_code in ['ar', 'hi', 'ko', 'es', 'tr']:
            # Use Stanza for these languages
            return StanzaIdentifier(language_code)
        else:
            return None