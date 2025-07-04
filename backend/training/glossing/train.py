import random
import tempfile
from pathlib import Path
from typing import List, Optional

import spacy
import srsly
from training.preprocessing import build_docbin

from spacy.tokens import DocBin
from spacy.training.corpus import Corpus
from spacy.training.initialize import init_nlp
from spacy.training.loop import train as train_nlp
from spacy.util import load_config
from wasabi import msg
from utils.functions import find_language, set_global_variables

METRICS = ["token_acc", "morph_acc"]
LANGUAGES, NO_LATIN, OBLIGATORY_COLUMNS = set_global_variables()

def chunk(l: List, n: int):
    """Split a list l into n chunks of fairly equal number of elements"""
    k, m = divmod(len(l), n)
    return (l[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n))


def get_all_except(l: List, idx: int):
    """Get all elements of a list except a given index"""
    return l[:idx] + l[(idx + 1):]


def flatten(l: List) -> List:
    """Flatten a list of lists"""
    return [item for sublist in l for item in sublist]

def train_spacy(
    input_dir: str,
    lang: str,
    study: str,
    pretrained_model: Optional[str] = None,
    shuffle: bool = True,
    use_gpu: int = 0,
    log_to_wandb: bool = True,
    wandb_project: str = "spacy-training",
):
    """
    Train a spaCy model on 90% of the data and evaluate on 10% test split.
    Optionally log metrics to Weights & Biases if available.
    """
    # Determine language code
    lang = find_language(lang, LANGUAGES)

    # Optional GPU setup
    from spacy.cli._util import setup_gpu
    if use_gpu >= 0:
        setup_gpu(use_gpu)
    else:
        msg.info("Using CPU mode.")

    # Initialize W&B if requested
    wandb_run = None
    if log_to_wandb:
        try:
            import wandb
            wandb_run = wandb.init(
                project=wandb_project,
                config={"language": lang, "study": study, "use_gpu": use_gpu}
            )
            msg.info("Initialized Weights & Biases logging")
        except ImportError:
            msg.warning("wandb not installed; skipping W&B logging")

    # Build binary docs from annotated data
    msg.info("Building DocBin from input directory")
    build_docbin(lang=lang, study=study, input_dir=input_dir)

    # Paths for data and config
    corpus_path = Path(f"training/data/{lang}_{study}_train.spacy")
    config_path = Path("training/glossing/configs/config.cfg")
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found at {config_path}")

    # Load or blank spaCy model
    if pretrained_model:
        nlp = spacy.load(pretrained_model)
    else:
        nlp = spacy.blank(lang)

    # Load all docs from corpus
    doc_bin = DocBin().from_disk(corpus_path)
    docs = list(doc_bin.get_docs(nlp.vocab))
    if shuffle:
        random.shuffle(docs)

    # Split into 90% train and 10% test
    total = len(docs)
    split_idx = int(total * 0.9)
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
        config = load_config(config_path)
        config["nlp"]["lang"] = lang
        config["paths"]["train"] = str(train_path)
        config["paths"]["dev"] = str(test_path)

        # Initialize and train on 90% split
        msg.divider("Training model on 90% of data")
        nlp_final = init_nlp(config)
        trained_nlp, _ = train_nlp(nlp_final, None, use_gpu=use_gpu)

        # Evaluate on 10% test set
        msg.info("Evaluating on 10% test set")
        from spacy.gold import Corpus
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

        if wandb_run:
            wandb_run.log(metrics_to_log)
            msg.good("Logged metrics to Weights & Biases")
            wandb_run.finish()

        # Save final model
        model_dir = Path(f"models/glossing/{lang}_{study}_custom_glossing")
        model_dir.mkdir(parents=True, exist_ok=True)
        trained_nlp.to_disk(model_dir)
        msg.good(f"Saved final model to {model_dir}")

    return scores


if __name__ == "__main__":
    lang = "german"
    study = "H"
    #input_dir = "C:/Users/camelo.cruz/Leibniz-ZAS/Leibniz Dream Data - Studies/H_Dependencies/H06a-Relative-Clause-Production-study/H06a_raw_files_deu"
    input_dir = '/Users/alejandra/Library/CloudStorage/OneDrive-FreigegebeneBibliotheken–Leibniz-ZAS/Leibniz Dream Data - Studies/tests_alejandra/german/H06a_deu_adults Kopie'
    train_spacy(input_dir=input_dir, lang=lang, study=study, n_folds=1, shuffle=True, use_gpu=0)