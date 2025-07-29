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
        self.train_config_path = Path(self.configs_dir / f'{self.lang}_{self.study}_config.cfg')
        self.models_dir = self.base_backend_dir / 'models'
        print(f'models_dir: {self.models_dir}')

    def _setup_gpu(self) -> None:
        if self.use_gpu >= 0:
            setup_gpu(self.use_gpu)
        else:
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
    
    def training_step(self, data_df):
        doc_bin = self.create_docbin(data_df)
        docs = list(doc_bin.get_docs(self.nlp.vocab))
        random.shuffle(docs)

        # Split into 95% train and 5% test
        total = len(docs)
        split_idx = int(total * 0.95)
        train_docs = docs[:split_idx]
        test_docs = docs[split_idx:]
        msg.info(f"Total docs: {total}, train: {len(train_docs)}, test: {len(test_docs)}")

        # Write out temporary train/test spacy files
        with tempfile.TemporaryDirectory() as tmpdir_str:
            tmpdir = Path(tmpdir_str)
            train_path = tmpdir / "train.spacy"
            test_path = tmpdir / "test.spacy"

            DocBin(docs=train_docs).to_disk(train_path)
            DocBin(docs=test_docs).to_disk(test_path)

            # Load and adjust config for training
            config = load_config(self.train_config_path)
            config["nlp"]["lang"] = self.lang
            config["paths"]["train"] = str(train_path)
            config["paths"]["dev"] = str(test_path)

            # Initialize and train on 90% split
            msg.divider("Training model on 90% of data")
            nlp_final = init_nlp(config)
            trained_nlp, _ = train_nlp(nlp_final, None, use_gpu=self.use_gpu)

            # Evaluate on 10% test set
            msg.info("Evaluating on 10% test set")
            from spacy.training.corpus import Corpus
            corpus = Corpus(str(test_path), gold_preproc=False)
            examples = list(corpus(trained_nlp))
            scores = trained_nlp.evaluate(examples)

            # Log metrics locally and to W&B
            metrics_to_log = {}
            for metric in METRICS:
                val = scores.get(metric)
                if val is not None:
                    msg.info(f"{metric}: {val:.3f}")
                    metrics_to_log[metric] = val

            # Save final model
            model_dir = Path(self.models_dir / 'glossing' / f'{self.lang}_{self.study}_custom_glossing')
            model_dir.mkdir(parents=True, exist_ok=True)
            trained_nlp.to_disk(model_dir)
            msg.good(f"Saved final model to {model_dir}")

        return scores