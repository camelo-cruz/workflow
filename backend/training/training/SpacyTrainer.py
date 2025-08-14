import math
import random
import tempfile
from pathlib import Path
from typing import Optional
import pandas as pd

import spacy
from spacy.cli._util import setup_gpu
from spacy.cli import download
from spacy.util import is_package

from spacy import util
from spacy.tokens import DocBin
from spacy.training.corpus import Corpus
from spacy.cli.debug_data import debug_data
from spacy.cli.init_config import fill_config
from spacy.training.initialize import init_nlp
from spacy.training.loop import train as train_nlp
from spacy.util import load_config
from wasabi import msg
from utils.functions import find_language, set_global_variables
from training.training.abstract import AbstractTrainer

METRICS = ["token_acc", "morph_acc"]
LANGUAGES, NO_LATIN, OBLIGATORY_COLUMNS = set_global_variables()

class SpacyTrainer(AbstractTrainer):
    DEFAULT_SPACY = {
            'de': 'de_core_news_lg',
            'en': 'en_core_web_lg',
            'fr': 'fr_core_news_lg',
            'zh': 'zh_core_web_lg',
            'el': 'el_core_news_lg',
            'it': 'it_core_news_lg',
            'ja': 'ja_core_news_lg',
            'pt': 'pt_core_news_lg',
            'ro': 'ro_core_news_lg',
            'ru': 'ru_core_news_lg',
            'uk': 'uk_core_news_lg'
        }
    
    def __init__(self, lang: str, study: str, use_gpu: int = 0, log_to_wandb: bool = True, wandb_project: str = "spacy-training"):
        super().__init__(lang, study, use_gpu, log_to_wandb, wandb_project)
        self.pretrained_model = False
        self.nlp = self._load_model()
        self.data = None

        self.base_training_dir = Path(__file__).resolve().parents[0]
        self.base_backend_dir = Path(__file__).resolve().parents[2]
        self.configs_dir = Path(self.base_training_dir) / 'spacy_configs'
        self.base_config_path = Path(self.configs_dir / 'base_config.cfg')
        self.train_config_path = Path(self.configs_dir / 'train_config.cfg')
        self.models_dir = self.base_backend_dir / 'models'
        print(f'models_dir: {self.models_dir}')

    def _setup_gpu(self) -> None:
        try:
            if self.use_gpu >= 0:
                setup_gpu(self.use_gpu)
            else:
                msg.info("Using CPU mode.")
        except Exception as e:
            msg.fail(f"Failed to set up GPU: {e}")
            msg.info("Using CPU mode.")
    
    def _load_model(self) -> str:
        if self.lang in self.DEFAULT_SPACY:
            pkg = self.DEFAULT_SPACY[self.lang]
            if not is_package(pkg):
                print(f"{pkg} not found — downloading…")
                download(pkg)
            self.pretrained_model = pkg
            msg.info(f"Using pretrained spaCy model: {pkg}")
            return spacy.load(pkg)
        else:
            return spacy.blank(self.lang)

    def create_docbin(self, data_df) -> DocBin:
        """Create a DocBin from the annotated data in the input directory."""
        docbin = DocBin(attrs=['MORPH'], store_user_data=True)

        for _, row in data_df.iterrows():
            text = row['clean_text']
            tokens = row['tokens']
            feats = row['UDfeats']
            doc = self.nlp(text)
            for token, feat in zip(doc, feats):
                token.set_morph(feat)
            docbin.add(doc)

        with tempfile.TemporaryDirectory() as tmpdir:
            out_spacy = Path(tmpdir) / f"{self.lang}_{self.study}_train.spacy"
            docbin.to_disk(out_spacy)
            msg.good(f"DocBin saved to {out_spacy}")
            cfg = util.load_config(self.base_config_path)
            cfg['nlp']['lang'] = self.lang
            cfg['paths']['train'] = cfg['paths']['dev'] = str(out_spacy)
            if self.pretrained_model:
                cfg['paths']['vectors'] = self.pretrained_model
            cfg.to_disk(self.train_config_path)
            fill_config(self.train_config_path, self.train_config_path)
            debug_data(self.train_config_path, silent=False, verbose=True)

        return docbin
    
    def _train_once(self, train_docs, dev_docs, seed=42):
        """Train a model once on the provided docs; return (trained_nlp, scores)."""
        with tempfile.TemporaryDirectory() as tmpdir_str:
            tmpdir = Path(tmpdir_str)
            train_path = tmpdir / "train.spacy"
            dev_path   = tmpdir / "dev.spacy"

            DocBin(docs=train_docs).to_disk(train_path)
            DocBin(docs=dev_docs).to_disk(dev_path)

            config = load_config(self.train_config_path)
            config["nlp"]["lang"] = self.lang
            config["paths"]["train"] = str(train_path)
            config["paths"]["dev"] = str(dev_path)
            # Optional: fix seeds for reproducibility
            config["training"]["seed"] = seed

            nlp_init = init_nlp(config)
            trained_nlp, _ = train_nlp(nlp_init, None, use_gpu=self.use_gpu)

            # Evaluate on dev_docs
            from spacy.training.corpus import Corpus
            corpus = Corpus(str(dev_path), gold_preproc=False)
            examples = list(corpus(trained_nlp))
            scores = trained_nlp.evaluate(examples)
            return trained_nlp, scores

    def training_step(self, data_df, seed=42):
        """
        strategy:
          - "cv_then_all" (recommended): K-fold CV to estimate performance, then retrain on ALL docs.
          - "all_only": use ALL docs for training and (for spaCy bookkeeping) also as dev.
        """
        # Build docs from DataFrame using your current pipeline
        doc_bin = self.create_docbin(data_df)
        docs = list(doc_bin.get_docs(self.nlp.vocab))

        # Shuffle once for reproducibility
        random.seed(seed)
        random.shuffle(docs)

        msg.divider("Training one final model on 100% of the data (dev==train)")
        trained_nlp, scores = self._train_once(train_docs=docs, dev_docs=docs, seed=seed)
        self._save_model(trained_nlp)
        self._log_metrics(scores, prefix="final(all)")
        msg.warn("Dev==Train: evaluation is optimistic; use CV for a real estimate.")
        return scores

    # ---- small helpers ----
    def _save_model(self, trained_nlp):
        model_dir = Path(self.models_dir / 'glossing' / f'{self.lang}_{self.study}_custom_glossing')
        model_dir.mkdir(parents=True, exist_ok=True)
        trained_nlp.to_disk(model_dir)
        msg.good(f"Saved final model to {model_dir}")

    def _log_metrics(self, scores: dict, prefix: str = ""):
        for metric in METRICS:
            val = scores.get(metric)
            if val is not None:
                msg.info(f"{prefix} {metric}: {val:.3f}")