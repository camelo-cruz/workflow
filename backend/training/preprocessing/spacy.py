import os
from pathlib import Path

import pandas as pd
import spacy
from spacy.tokens import DocBin
from spacy.cli.debug_data import debug_data
from spacy.cli.init_config import fill_config
from spacy import util
from wasabi import msg

from utils.functions import (
    load_glossing_rules,
    find_language,
    set_global_variables,
)

from training.preprocessing.abstract import BasePreprocessor

class GlossingPreprocessor(BasePreprocessor):
    """
    Preprocess glossing data to produce a spaCy DocBin and feature Excel.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Load Leipzig glossary
        self.LEIPZIG_GLOSSARY = load_glossing_rules("LEIPZIG_GLOSSARY.json")
        self.LEIPZIG2UD = {
            entry["leipzig"]: (entry["category"], key)
            for key, entry in self.LEIPZIG_GLOSSARY.items()
        }
        self.base_config_path = Path(__file__).parent.parent / 'glossing' / 'configs' / 'glossing_config.cfg'
        self.tokens_without_gloss: set[str] = set()
        self.unknown_codes: set[str] = set()
        self.pretrained_model = self._default_model()

    
    def _default_model(self) -> str:
        if self.lang == "de":
            return "de_core_news_lg"
        if self.lang == "en":
            return "en_core_web_lg"
        else:
            return None

    def _map_gloss(self, gloss: str) -> list[str]:
        if not isinstance(gloss, str):
            return []
        feats = []
        for token in gloss.split():
            is_gloss = '.' in token or token.isupper() or any(c.isdigit() for c in token)
            if not is_gloss:
                feats.append('')
                self.tokens_without_gloss.add(token)
                continue
            parts = [c.upper() for c in token.split('.') if c]
            if parts and parts[0].islower():
                parts.pop(0)
            mapped = []
            for code in parts:
                pair = self.LEIPZIG2UD.get(code)
                if pair:
                    mapped.append(f"{pair[0]}={pair[1]}")
                else:
                    self.unknown_codes.add(code)
            feats.append('|'.join(mapped) if mapped else '')
        return feats

    def preprocess(self) -> None:
        log_path = self.input_dir / 'glossing_traindata.log'
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = self._setup_file_handler(log_path)
 
        nlp = spacy.load(self.pretrained_model) if self.pretrained_model else spacy.blank(self.lang)
        self.logger.info(f"Using model: {self.pretrained_model or 'blank'}")

        docbin = DocBin(attrs=['MORPH'], store_user_data=True)
        examples = []

        for root, _, files in os.walk(self.input_dir):
            for fname in files:
                if not fname.endswith('annotated.xlsx'):
                    continue
                df = pd.read_excel(Path(root) / fname, nrows=60).dropna(
                    subset=[self.TEXT_COLUMN, self.GLOSS_COLUMN]
                )
                texts = [line for t in df[self.TEXT_COLUMN].map(self._clean_text)
                         for line in t.split('\n') if line.strip()]
                glosses = [line for g in df[self.GLOSS_COLUMN].map(self._clean_text)
                           for line in g.split('\n') if line.strip()]
                if len(texts) != len(glosses):
                    msg.warn(f"Skipped {fname}: {len(texts)} vs {len(glosses)}")
                    self.logger.warning(f"Skipped {fname}: {len(texts)} vs {len(glosses)}")
                    continue
                for text, gloss in zip(texts, glosses):
                    feats = self._map_gloss(gloss)
                    doc = nlp(text)
                    if len(doc) != len(feats):
                        msg.warn(f"Token mismatch: '{text}'")
                        self.logger.warning(f"Token mismatch: '{text}'")
                        continue
                    for token, feat in zip(doc, feats):
                        token.set_morph(feat)
                    docbin.add(doc)
                    examples.append({'text': text, 'gloss': ' '.join(feats)})

        if examples:
            out_xlsx = Path('training/data') / f"{self.lang}_{self.study}_gloss_features.xlsx"
            pd.DataFrame(examples).to_excel(out_xlsx, index=False)
        out_spacy = Path(__file__).parent / 'data' / f"{self.lang}_{self.study}_train.spacy"
        docbin.to_disk(out_spacy)

        msg.good(f"Built Gloss DocBin: {len(docbin)} docs")
        if self.tokens_without_gloss:
            msg.warn(f"Tokens without gloss: {self.tokens_without_gloss}")
            self.logger.info(f"Built Gloss DocBin: {len(docbin)} docs")
        if self.unknown_codes:
            msg.warn(f"Unknown gloss codes: {self.unknown_codes}")
            self.logger.info(f"Unknown gloss codes: {self.unknown_codes}")

        # spaCy config and debug
        cfg = util.load_config(self.base_config_path)
        cfg['nlp']['lang'] = self.lang
        cfg['paths']['train'] = cfg['paths']['dev'] = str(out_spacy)
        if self.pretrained_model:
            cfg['paths']['vectors'] = self.pretrained_model
        cfg.to_disk('training/glossing/configs/config.cfg')
        fill_config('training/glossing/configs/config.cfg', 'training/glossing/configs/config.cfg')
        debug_data('training/glossing/configs/config.cfg', silent=False, verbose=True)

        handler.close()
        self.logger.removeHandler(handler)