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

METRICS = ["token_acc", "morph_acc"]


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
    n_folds: int = 10,
    shuffle: bool = False,
    use_gpu: int = 0,
):
    # Optional GPU setup
    from spacy.cli._util import setup_gpu
    if use_gpu >= 0:
        setup_gpu(use_gpu)
    else:
        msg.info("Using CPU mode.")
    
    build_docbin(lang=lang, study=study, input_dir=input_dir)

    # Paths
    corpus_path = Path(f"training/data/{lang}_{study}_train.spacy")
    output_path = Path(f"training/data/{lang}_{study}_cv_scores.json")
    config_path = Path("training/glossing/configs/config.cfg")
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found at {config_path}")

    # Load or blank nlp
    if pretrained_model:
        nlp = spacy.load(pretrained_model)
    else:
        nlp = spacy.blank(lang)

    # Load docs
    doc_bin = DocBin().from_disk(corpus_path)
    docs = list(doc_bin.get_docs(nlp.vocab))
    if shuffle:
        random.shuffle(docs)

    # Cross-validation
    if n_folds > 1:
        folds = list(chunk(docs, n_folds))
        all_scores = {metric: [] for metric in METRICS}

        for idx, fold in enumerate(folds):
            dev = fold
            train_docs = flatten(get_all_except(folds, idx))
            msg.divider(f"Fold {idx+1}, train: {len(train_docs)}, dev: {len(dev)}")

            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir = Path(tmpdir)
                train_path = tmpdir / "train.spacy"
                dev_path = tmpdir / "dev.spacy"

                DocBin(docs=train_docs).to_disk(train_path)
                DocBin(docs=dev).to_disk(dev_path)
                msg.good(f"Wrote temp data to {train_path} and {dev_path}")

                msg.info("Training model for this fold")
                config = load_config(config_path)
                config["nlp"]["lang"] = lang
                config["paths"]["train"] = str(train_path)
                config["paths"]["dev"] = str(dev_path)

                fold_nlp = init_nlp(config)
                fold_nlp, _ = train_nlp(fold_nlp, None, use_gpu=use_gpu)

                msg.info("Evaluating on dev set")
                corpus = Corpus(str(dev_path), gold_preproc=False)
                examples = list(corpus(fold_nlp))
                scores = fold_nlp.evaluate(examples)

                for metric in METRICS:
                    val = scores.get(metric)
                    if val is not None:
                        all_scores[metric].append(val)

        msg.info(f"Computing average {n_folds}-fold CV score")
        avg_scores = {}
        for metric, scores in all_scores.items():
            valid = [s for s in scores if s is not None]
            avg_scores[metric] = sum(valid) / len(valid) if valid else 0.0

        msg.table(avg_scores.items(), header=("Metric", "Score"))
        srsly.write_json(output_path, avg_scores)
        msg.good(f"Saved CV results to {output_path}")

    # Final train on all data
    msg.divider("Training final model on all data")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        full_train_path = tmpdir / "train_full.spacy"
        DocBin(docs=docs).to_disk(full_train_path)

        config = load_config(config_path)
        config["nlp"]["lang"] = lang
        config["paths"]["train"] = str(full_train_path)
        config["paths"]["dev"] = str(full_train_path)

        final_nlp = init_nlp(config)
        final_nlp, _ = train_nlp(final_nlp, None, use_gpu=use_gpu)

        model_dir = Path(f"models/glossing/{lang}_{study}_custom_glossing")
        model_dir.mkdir(parents=True, exist_ok=True)
        final_nlp.to_disk(model_dir)
        msg.good(f"Saved final model to {model_dir}")


if __name__ == "__main__":
    lang = "de"
    study = "H"
    #input_dir = "C:/Users/camelo.cruz/Leibniz-ZAS/Leibniz Dream Data - Studies/H_Dependencies/H06a-Relative-Clause-Production-study/H06a_raw_files_deu"
    input_dir = '/Users/alejandra/Library/CloudStorage/OneDrive-FreigegebeneBibliotheken–Leibniz-ZAS/Leibniz Dream Data - Studies/tests_alejandra/german/H06a_deu_adults Kopie'
    train_spacy(input_dir=input_dir, lang=lang, study=study, n_folds=1, shuffle=True, use_gpu=0)