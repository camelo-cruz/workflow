import os
import re
import sys
import logging
from pathlib import Path

from spacy.language import Language

from utils.functions import (
    load_glossing_rules,
    find_language,
    set_global_variables,
)
from abc import ABC, abstractmethod


class BasePreprocessor(ABC):
    """
    Abstract base class for data preprocessing:
      - Sets up paths, language, logging, and text cleaning utilities.
    """
    TEXT_COLUMN = "latin_transcription_utterance_used"
    GLOSS_COLUMN = "glossing_utterance_used"
    TRANSLATION_COLUMN = "translation_utterance_used"

    def __init__(
        self,
        input_dir: str,
        lang: str,
        study: str,
        base_config_path: str,
        pretrained_model: Language | str = None,
    ):
        self.input_dir = Path(input_dir)
        self.study = study

        # Language setup
        self.LANGUAGES, self.NO_LATIN, self.OBLIGATORY_COLUMNS = set_global_variables()
        self.lang = find_language(lang, self.LANGUAGES)

        # Ensure UTF-8
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')

        # Logger configuration
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.INFO)

        # Model selection
        self.pretrained_model = pretrained_model or self._default_model()

        # Base config path for spaCy pipelines
        self.base_config_path = Path(base_config_path)

    def _default_model(self) -> str:
        if self.lang == "de":
            return "de_core_news_lg"
        if self.lang == "en":
            return "en_core_web_lg"
        return ''

    def _setup_file_handler(self, filepath: Path) -> logging.FileHandler:
        handler = logging.FileHandler(filepath, encoding='utf-8')
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        self.logger.addHandler(handler)
        return handler

    def _clean_text(self, text: str) -> str:
        if not isinstance(text, str):
            return ''
        text = text.replace('..', '.')
        text = text.replace(',', '')
        text = re.sub(r'\s+', ' ', text)
        text = text.strip().strip('.')
        text = re.sub(r"[\[\]\(\)\{\}]", '', text)
        text = re.sub(r"^\d+\s*", '', text)
        text = re.sub(r"\b(\d)(SG|PL)\b", r"\1.\2", text)
        return text.strip()

    @abstractmethod
    def preprocess(self) -> None:
        """Run the preprocessing routine."""
        pass