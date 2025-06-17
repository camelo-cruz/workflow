import random
import tempfile
import os
import pandas as pd
import spacy
import srsly
import re
import logging
import string
from pathlib import Path
from spacy.tokens import DocBin
from spacy.training.corpus import Corpus
from spacy.training.initialize import init_nlp
from spacy.training.loop import train as train_nlp
from spacy.util import load_config
from spacy.cli._util import setup_gpu, show_validation_error
from wasabi import msg
from utils.functions import load_glossing_rules, setup_logging

# Load mapping resources
LEIPZIG_GLOSSARY = load_glossing_rules("LEIPZIG_GLOSSARY.json")
SPACY2CATEGORY = load_glossing_rules("VALUE2FEATURE.json")
LEIPZIG2SPACY = {v: k for k, v in LEIPZIG_GLOSSARY.items()}

script_dir = Path(__file__).parent

# Metrics to collect during evaluation
METRICS = ["token_acc", "morph_acc"]

logger = logging.getLogger(__name__)

def clean_text(text: str) -> str:
    """
    Clean a glossed string by removing newlines, digits, and punctuation.
    Handles non-str or missing inputs by returning an empty string.
    """
    if not isinstance(text, str):
        return ""
    text = re.sub(r"\d+", "", text)  # remove numbers
    text = text.replace("..", ".") # replace double dots with single dot
    text = re.sub(r"[\[\]\(\)\{\}]", "", text) # remove brackets
    text = text.replace(",", "")  # replace newlines with space
    text = text.strip().strip('.')
    text = text.lower()  # convert to lowercase
    return text.strip()


def gloss_to_ud_features(gloss: str) -> list[str]:
    if not isinstance(gloss, str):
        return []

    per_token_feats: list[str] = []
    token_without_gloss: list[str] = []
    unknown_codes: list[str] = []
    for token in gloss.split():
        # Case 1: no “.” ⇒ not glossed
        if "." not in token:
            per_token_feats.append('')
            token_without_gloss.append(token)
            continue

        # Case 2: has gloss, map each code
        codes = [c.upper() for c in token.split(".")[1:]]  # Convert codes to uppercase
        feats: list[str] = []
        for code in codes:
            spacy_value = LEIPZIG2SPACY.get(code)
            feat_name   = SPACY2CATEGORY.get(spacy_value)
            if spacy_value and feat_name:
                feats.append(f"{feat_name}={spacy_value}")
            else:
                unknown_codes.append(code)

        # If no features mapped, use “_” as placeholder
        per_token_feats.append("|".join(feats) if feats else "_")

    logger.debug(f"tokens without gloss: {token_without_gloss}")
    logger.debug(f"unknown codes: {unknown_codes}")

    return per_token_feats


def build_docbin(lang: str, input_dir: str) -> DocBin:
    nlp = spacy.blank(lang)
    docbin = DocBin(attrs=["MORPH"], store_user_data=True)
    all_examples = []

    for root, dirs, files in os.walk(input_dir):
        for fname in files:
            if not fname.endswith("annotated.xlsx"):
                continue

            base = os.path.abspath(os.path.join(root, '..'))
            file_path = os.path.join(root, fname)
            log_path = os.path.join(base, "transcription.log")
            logging_fh = setup_logging(logger, log_path)
            df = pd.read_excel(file_path, nrows=60)
            df = df.dropna(subset=["latin_transcription_utterance_used", "glossing_utterance_used"])

            raw_texts = df["latin_transcription_utterance_used"].astype(str).tolist()
            raw_glosses = df["glossing_utterance_used"].astype(str).tolist()

            cleaned_texts = []
            for t in raw_texts:
                t_clean = clean_text(t)
                lines = [line.strip() for line in t_clean.split("\n") if line.strip()]
                cleaned_texts.extend(lines)

            cleaned_glosses = []
            for g in raw_glosses:
                g_clean = clean_text(g)
                gloss_lines = [line.strip() for line in g_clean.split("\n") if line.strip()]
                cleaned_glosses.extend(gloss_lines)
            

            if len(cleaned_texts) != len(cleaned_glosses):
                raise ValueError(f"Mismatch in lengths: {len(cleaned_texts)} texts vs {len(cleaned_glosses)} glosses in file {file_path}")
            else:
                msg.good(f"Matched {len(cleaned_texts)} texts with {len(cleaned_glosses)} glosses in file {file_path}")
                logger.info(f"Processing {len(cleaned_texts)} texts and glosses from {file_path}")
            
            # Build DataFrame
            inspect_df = pd.DataFrame({
                "cleaned_text": cleaned_texts,
                "cleaned_gloss": cleaned_glosses
            })

            # Save to Excel for full inspection
            inspect_df.to_excel(script_dir / "data" / "cleaned_inspection.xlsx", index=False)

            feats_list = [gloss_to_ud_features(g) for g in cleaned_glosses]

            for text, feats in zip(cleaned_texts, feats_list):
                doc = nlp(text)
                if len(doc) != len(feats):
                    raise ValueError(f"Token count mismatch in row: '{text}' has {len(doc)} tokens but {len(feats)} in file {file_path}")
                for token, feat in zip(doc, feats):
                    token.set_morph(feat)
                docbin.add(doc)
                all_examples.append({"text": text, "gloss": " ".join(feats)})
    
    # Save examples to Excel
    #if all_examples:
        pd.DataFrame(all_examples).to_excel(script_dir / "data" / "train.xlsx", index=False)

    msg.good(f"Built DocBin with {len(docbin)} documents from {input_dir}")
    print("Total examples:", len(list(docbin.get_docs(nlp.vocab))))
    return docbin

def chunk(items: list, n: int):
    """Split items into n roughly equal chunks."""
    k, m = divmod(len(items), n)
    return [items[i*k + min(i, m):(i+1)*k + min(i+1, m)] for i in range(n)]


def flatten(list_of_lists: list[list]):
    """Flatten one level of nesting."""
    return [x for sub in list_of_lists for x in sub]


def run_training(
    lang: str,
    data_dir: str,
    model: str = None,   # ← new arg: path to an existing spaCy model
    n_folds: int = 10,
    shuffle: bool = False,
    use_gpu: int = 0,
):
    script_dir = Path(__file__).parent
    config_path = str(script_dir / "config.cfg")
    output_path = str(script_dir / "output" / f"results-{lang}.json")
    os.makedirs(Path(output_path).parent, exist_ok=True)
    setup_gpu(use_gpu)

    # build data
    docbin = build_docbin(lang, data_dir)
    docs = list(docbin.get_docs(spacy.blank(lang).vocab))
    if shuffle:
        random.shuffle(docs)
    folds = chunk(docs, n_folds)
    all_scores = {m: [] for m in METRICS}

    for idx, dev in enumerate(folds):
        train = flatten([f for i, f in enumerate(folds) if i != idx])
        msg.divider(f"Fold {idx+1} — train {len(train)}, dev {len(dev)}")

        with tempfile.TemporaryDirectory() as tmpdir:
            train_path = os.path.join(tmpdir, "train.spacy")
            dev_path   = os.path.join(tmpdir, "dev.spacy")
            DocBin(docs=train).to_disk(train_path)
            DocBin(docs=dev).to_disk(dev_path)

            if model:
                msg.info(f"Loading base model from {model}")
                nlp = spacy.load(model)
                config = nlp.config
                overrides = {
                    "paths.train": train_path,
                    "paths.dev":   dev_path,
                    "nlp.lang":    lang,
                }
            else:
                overrides = {
                    "paths.train": train_path,
                    "paths.dev":   dev_path,
                    "nlp.lang":    lang,
                }

            with show_validation_error(config_path, hint_fill=False):
                config = load_config(config_path, overrides, interpolate=False)
                
            nlp = init_nlp(config)

            # Now you have a valid config with train/dev paths set:
            nlp, _ = train_nlp(nlp, None)

            corpus = Corpus(dev_path, gold_preproc=False)
            scores = nlp.evaluate(list(corpus(nlp)))
            for m in METRICS:
                all_scores[m].append(scores.get(m, 0.0))


    # report averages
    avg = {m: sum(v if v is not None else 0.0 for v in vals)/len(vals)
           for m, vals in all_scores.items()}
    msg.table(avg, header=("Metric","Score"))
    srsly.write_json(output_path, avg)
    msg.good(f"Saved results to {output_path}")

    # save the last nlp to disk
    output_name = f"{lang}_custom_glossing" if not model else f"{model}_custom_glossing"
    model_output = script_dir / "models" / output_name
    os.makedirs(model_output, exist_ok=True)
    nlp.to_disk(model_output)
    msg.good(f"Saved trained model to {model_output}")



if __name__ == "__main__":
    run_training(lang="de", 
                data_dir='/Users/alejandra/Library/CloudStorage/OneDrive-FreigegebeneBibliotheken–Leibniz-ZAS/Leibniz Dream Data - Studies/tests_alejandra/german/Session_1152193 glossing',
                #model="de_dep_news_trf",
                n_folds=5, shuffle=True, use_gpu=0)