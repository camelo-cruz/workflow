import math
import random
import tempfile
from pathlib import Path
from typing import Optional
import sys

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
from spacy.util import compile_infix_regex, get_lang_class
from wasabi import msg

from utils.functions import find_language, set_global_variables
from training.training.abstract import AbstractTrainer

METRICS = ["token_acc", "morph_acc"]
LANGUAGES, NO_LATIN, OBLIGATORY_COLUMNS = set_global_variables()


class SpacyTrainer(AbstractTrainer):
    DEFAULT_SPACY = {
        "de": "de_core_news_lg",
        "en": "en_core_web_lg",
        "fr": "fr_core_news_lg",
        "zh": "zh_core_web_lg",
        "el": "el_core_news_lg",
        "it": "it_core_news_lg",
        "ja": "ja_core_news_lg",
        "pt": "pt_core_news_lg",
        "ro": "ro_core_news_lg",
        "ru": "ru_core_news_lg",
        "uk": "uk_core_news_lg",
    }

    def __init__(
        self,
        lang: str,
        study: str,
        use_gpu: int = 0,
        log_to_wandb: bool = True,
        wandb_project: str = "spacy-training",
        preserve_hyphenated: bool = True,
    ):
        super().__init__(lang, study, use_gpu, log_to_wandb, wandb_project)
        self.pretrained_model: Optional[str] = None  # name of vectors pkg if used
        self.data = None

        self.base_training_dir = Path(__file__).resolve().parents[0]
        self.base_backend_dir = Path(__file__).resolve().parents[2]
        self.configs_dir = self.base_training_dir / "spacy_configs"
        self.base_config_path = self.configs_dir / "base_config.cfg"
        self.base_config_pretrained_path = self.configs_dir / "base_config_pretrained.cfg"
        self.train_config_path = self.configs_dir / "train_config.cfg"
        self.models_dir = self.base_backend_dir / "models"
        print(f"models_dir: {self.models_dir}")

        # Build pipeline and force tokenizer parity with preprocessor
        self.nlp = self._load_model(preserve_hyphenated=preserve_hyphenated)

    # ---------------- GPU ----------------
    def _setup_gpu(self) -> None:
        try:
            if self.use_gpu >= 0:
                setup_gpu(self.use_gpu)
            else:
                msg.info("Using CPU mode.")
        except Exception as e:
            msg.fail(f"Failed to set up GPU: {e}")
            msg.info("Using CPU mode.")


    def _load_model(self, preserve_hyphenated: bool) -> spacy.language.Language:
        """Load a pipeline (vectors if available), then force the tokenizer to blank(lang)."""
        if self.lang in self.DEFAULT_SPACY:
            pkg = self.DEFAULT_SPACY[self.lang]
            if not is_package(pkg):
                print(f"{pkg} not found — downloading…")
                download(pkg)
            nlp = spacy.load(pkg)
            self.pretrained_model = pkg  # keep handle to vectors package
            msg.info(f"Using pretrained spaCy model: {pkg}")
        else:
            nlp = spacy.blank(self.lang)
            self.pretrained_model = None
            msg.info(f"Using blank spaCy pipeline for lang='{self.lang}'")

        # 🔒 Force tokenizer parity with your preprocessor:
        tok_nlp = spacy.blank(self.lang)
        nlp.tokenizer = tok_nlp.tokenizer
        msg.info(f"Tokenizer set to blank('{self.lang}') with parity tweaks.")
        return nlp

    def create_docbin(self, data_df) -> DocBin:
        """Create a DocBin from the annotated data in the input directory."""
        docbin = DocBin(attrs=['MORPH'], store_user_data=True)

        for _, row in data_df.iterrows():
            text = row['clean_text']
            feats = row['UDfeats']
            doc = self.nlp.make_doc(text)


            #Debug: Check tokenization matches your 'tokens' list
            print("\n--- DEBUG DOC ---")
            print("TEXT:", text)
            print("TOKENS FROM NLP:", [t.text for t in doc])

            # Assign morphology
            for token, feat in zip(doc, feats):
                token.set_morph(feat)

            # Debug: Check morphological features assigned
            for token in doc:
                print(f"{token.text:<15} {token.morph}")

            print("--- END DEBUG ---\n")
            docbin.add(doc)

        with tempfile.TemporaryDirectory() as tmpdir:
            out_spacy = Path(tmpdir) / f"{self.lang}_{self.study}_train.spacy"
            docbin.to_disk(out_spacy)
            msg.good(f"DocBin saved to {out_spacy}")
            cfg = util.load_config(self.base_config_path)
            #if self.pretrained_model:
            #    cfg = util.load_config(self.base_config_pretrained_path)
            #    cfg['paths']['vectors'] = self.pretrained_model
            cfg['nlp']['lang'] = self.lang
            cfg['paths']['train'] = cfg['paths']['dev'] = str(out_spacy)

            cfg.to_disk(self.train_config_path)
            fill_config(self.train_config_path, self.train_config_path)

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

            # 👉 Run debug_data on the actual split
            filled_cfg_path = tmpdir / "config_for_debug.cfg"
            config.to_disk(filled_cfg_path)
            debug_data(str(filled_cfg_path), silent=False, verbose=True)

            nlp_init = init_nlp(config)
            trained_nlp, _ = train_nlp(nlp_init, None, use_gpu=self.use_gpu)

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

        dev_frac = 0.1  # 10% for dev set
        n = len(docs)
        dev_n = max(1, int(n * dev_frac))  # 10% for dev
        dev_docs = docs[:dev_n]
        train_docs = docs[dev_n:]

        msg.divider(f"Train/dev split: {len(train_docs)} / {len(dev_docs)} (dev={dev_frac:.0%})")

        trained_nlp, scores = self._train_once(train_docs=train_docs, dev_docs=dev_docs, seed=seed)
        self._save_model(trained_nlp)
        self._log_metrics(scores, prefix="heldout(10%)")
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