import random
import tempfile
from pathlib import Path
from typing import List, Optional

import spacy
import srsly
import typer
from training.glossing.preprocessing import build_docbin

from spacy.tokens import DocBin
from spacy.training.corpus import Corpus
from spacy.training.initialize import init_nlp
from spacy.training.loop import train as train_nlp
from spacy.util import load_config
from wasabi import msg

METRICS = ["token_acc", "pos_acc", "morph_acc", "tag_acc", "dep_uas", "dep_las"]


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


def train(
    lang: str,
    n_folds: int = 10,
    shuffle: bool = False,
    use_gpu: int = 0,
):
    if n_folds <= 1:
        raise ValueError("Number of folds must be greater than 1.")

    from spacy.cli._util import setup_gpu
    setup_gpu(use_gpu)

    # Set paths explicitly
    corpus_path = Path("training/glossing/data/train.spacy")
    config_path = Path("training/glossing/config.cfg")
    output_path = Path("training/glossing/data/cv_scores.json")

    # Load corpus
    empty_nlp = spacy.blank(lang)
    doc_bin = DocBin().from_disk(corpus_path)
    docs = list(doc_bin.get_docs(empty_nlp.vocab))
    if shuffle:
        random.shuffle(docs)

    folds = list(chunk(docs, n_folds))
    all_scores = {metric: [] for metric in METRICS}

    for idx, fold in enumerate(folds):
        dev = fold
        train = flatten(get_all_except(folds, idx))

        msg.divider(f"Fold {idx+1}, train: {len(train)}, dev: {len(dev)}")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            train_path = tmpdir / "train.spacy"
            dev_path = tmpdir / "dev.spacy"

            DocBin(docs=train).to_disk(train_path)
            DocBin(docs=dev).to_disk(dev_path)
            msg.good(f"Wrote temp data to {train_path} and {dev_path}")

            msg.info("Training model")
            config = load_config(config_path)
            config["paths"]["train"] = str(train_path)
            config["paths"]["dev"] = str(dev_path)

            nlp = init_nlp(config)
            nlp, _ = train_nlp(nlp, None)

            msg.info("Evaluating on dev set")
            corpus = Corpus(str(dev_path), gold_preproc=False)
            examples = list(corpus(nlp))
            gold_examples = [eg.reference for eg in examples]
            scores = nlp.evaluate(gold_examples)

            for metric in METRICS:
                if metric in scores:
                    all_scores[metric].append(scores[metric])

    msg.info(f"Computing average {n_folds}-fold CV score")
    avg_scores = {
        metric: sum(scores) / len(scores) if scores else 0.0
        for metric, scores in all_scores.items()
    }
    msg.table(avg_scores.items(), header=("Metric", "Score"))

    srsly.write_json(output_path, avg_scores)
    msg.good(f"Saved results to {output_path}")


if __name__ == "__main__":
    # Example hardcoded call for script use
    lang = "de"
    input_dir = "/Users/alejandra/Library/CloudStorage/OneDrive-FreigegebeneBibliotheken–Leibniz-ZAS/Leibniz Dream Data - Studies/F_Negative_Concepts/F07a-Comparatives/F07a_deu"
    build_docbin(lang=lang, input_dir=input_dir)
    train(lang=lang, n_folds=10, shuffle=True, use_gpu=-1)
