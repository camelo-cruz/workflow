import os
import random
import tempfile
from pathlib import Path
from typing import Optional, Dict

from abc import ABC, abstractmethod
import spacy
from spacy import util
from spacy.tokens import DocBin
from spacy.cli import download
from spacy.util import is_package, load_config
from spacy.cli.debug_data import debug_data
from spacy.cli.init_config import fill_config
from spacy.training.initialize import init_nlp
from spacy.training.loop import train as train_nlp
from spacy.cli._util import setup_gpu
from wasabi import msg

from training.trainer.abstract import AbstractTrainer
from utils.functions import find_language, set_global_variables

METRICS = ["token_acc", "morph_acc"]
LANGUAGES, NO_LATIN, OBLIGATORY_COLUMNS = set_global_variables()

class SpacyTrainer(AbstractTrainer):
    """
    Concrete Trainer for spaCy glossing models.

    Inherits GPU/W&B setup and run workflow from AbstractTrainer.
    """
    DEFAULT_SPACY = {
        'de': 'de_core_news_lg', 'en': 'en_core_web_lg', 'fr': 'fr_core_news_lg',
        'zh': 'zh_core_news_lg', 'el': 'el_core_news_lg', 'it': 'it_core_news_lg',
        'ja': 'ja_core_news_lg', 'pt': 'pt_core_news_lg', 'ro': 'ro_core_news_lg',
        'ru': 'ru_core_news_lg', 'uk': 'uk_core_news_lg'
    }

    def __init__(
        self,
        lang: str,
        study: str,
        log_to_wandb: bool = True,
        wandb_project: str = "spacy-training",
    ):
        super().__init__(lang, study, log_to_wandb, wandb_project)
        # Paths for config, data, and model
        base_dir = Path(__file__).parents[1]
        self.base_config_path = base_dir / 'glossing' / 'configs' / 'base_config.cfg'
        self.output_config_path = Path(base_dir / 'glossing' / 'configs' / f'{self.lang}_{self.study}_config.cfg')
        self.output_data_path = Path(self.data_dir / f'{self.lang}_{self.study}_data')
        self.model_dir = Path(self.models_dir / 'glossing' / f'{self.lang}_{self.study}_custom_glossing')

        self.pretrained_model = self._load_pretrained(self.lang)

    def _load_pretrained(self, model_key: str) -> Optional[str]:
        """
        Load or download a default spaCy package, or verify a custom model directory.
        Returns the model name or path for spacy.load().
        """
        if model_key in self.DEFAULT_SPACY:
            pkg = self.DEFAULT_SPACY[model_key]
            if not is_package(pkg):
                msg.info(f"SpaCy model {pkg} not found – downloading...")
                download(pkg)
            return pkg
        else:
            return None
    
    def _setup_gpu(self) -> None:
        spacy.prefer_gpu()

    def _prepare_config(self) -> None:
        """
        Load base config, set paths, and write out debugged config.
        """
        cfg = util.load_config(self.base_config_path)
        cfg['nlp']['lang'] = self.lang
        cfg['paths']['train'] = cfg['paths']['dev'] = str(self.output_data_path)
        if self.pretrained_model:
            cfg['paths']['vectors'] = self.pretrained_model
        cfg.to_disk(self.base_config_path)
        fill_config(self.base_config_path, self.base_config_path)
        debug_data(self.base_config_path, silent=False, verbose=True)

    def _make_docbins(self, corpus_path: Path, shuffle: bool = True) -> Dict[str, Path]:
        """
        Split .spacy docs in corpus_path into train/dev and return file paths.
        """
        nlp = spacy.load(self.pretrained_model) if self.pretrained_model else spacy.blank(self.lang)
        docs = list(DocBin().from_disk(corpus_path).get_docs(nlp.vocab))
        if shuffle:
            random.shuffle(docs)
        split_idx = int(len(docs) * 0.9)
        train_docs, dev_docs = docs[:split_idx], docs[split_idx:]

        tmpdir = Path(tempfile.mkdtemp(prefix=f"spacy_split_{self.lang}_{self.study}_"))
        train_path = tmpdir / "train.spacy"
        dev_path = tmpdir / "dev.spacy"
        DocBin(docs=train_docs).to_disk(train_path)
        DocBin(docs=dev_docs).to_disk(dev_path)
        msg.info(f"Docs split: train={len(train_docs)}, dev={len(dev_docs)}")
        return {"train": train_path, "dev": dev_path}

    def train(self) -> Dict[str, float]:
        """
        Full training workflow using configured paths and AbstractTrainer.run logic.
        """
        splits = self._make_docbins(Path(self.output_data_path))
        # 1. Prepare spaCy config
        self._prepare_config()
        # 2. Ensure data folder exists
        corpus_files = list(Path(self.output_data_path).glob("*.spacy"))
        if not corpus_files:
            raise FileNotFoundError(f"No .spacy files found in {self.output_data_path}")
        # 4. Load and train
        config = load_config(self.output_config_path)
        config['nlp']['lang'] = self.lang
        config['paths']['train'] = str(splits['train'])
        config['paths']['dev'] = str(splits['dev'])
        nlp = init_nlp(config)
        msg.divider("Training started")
        trained_nlp, _ = train_nlp(nlp, None, use_gpu=self.use_gpu)
        # 5. Evaluate
        from spacy.training.corpus import Corpus
        corpus = Corpus(str(splits['dev']), gold_preproc=False)
        examples = list(corpus(trained_nlp))
        scores = trained_nlp.evaluate(examples)
        metrics = {m: scores[m] for m in METRICS if m in scores}
        for m, v in metrics.items():
            msg.info(f"{m}: {v:.3f}")
        # 6. Save model
        self.model_dir.mkdir(parents=True, exist_ok=True)
        trained_nlp.to_disk(self.model_dir)
        msg.good(f"Saved model to {self.model_dir}")
        return metrics
