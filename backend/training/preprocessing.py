import os
from wasabi import msg
import pandas as pd
import spacy
import re
import logging
import tempfile
from pathlib import Path
from spacy.tokens import DocBin
from utils.functions import load_glossing_rules, setup_logging
from spacy.cli.debug_data import debug_data
from spacy.cli.init_config import fill_config
from spacy.language import Language
from spacy import util
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

SCRIPT_PATH = Path(__file__).parent
PARENT_PATH = SCRIPT_PATH.parent
BASE_CONFIG_PATH = SCRIPT_PATH / "glossing/configs/base_config.cfg"

TEXT_COLUMN = "latin_transcription_utterance_used"
GLOSS_COLUMN = "glossing_utterance_used"
TRANSLATION_COLUMN = "translation_utterance_used"

# Load mapping resources
LEIPZIG_GLOSSARY = load_glossing_rules("LEIPZIG_GLOSSARY.json")
LEIPZIG2UD: dict[str, tuple[str,str]] = {
    entry["leipzig"]: (entry["category"], key)
    for key, entry in LEIPZIG_GLOSSARY.items()
}

TOKEN_WITHOUT_GLOSS: set[str] = set() # Initialize set to store tokens without gloss
UNKNOWN_CODES: set[str] = set() # Initialize set to store unknown codes. This means that the code is not in our list of LEIPZIG_GLOSSARY and needs to be added

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def setup_file_logger(log_path: str) -> logging.FileHandler:
    fh = logging.FileHandler(log_path, encoding='utf-8')
    fh.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh.setFormatter(formatter)
    return fh

def clean_text(text: str) -> str:
    """
    Clean a glossed string by removing newlines, digits, and punctuation.
    Handles non-str or missing inputs by returning an empty string.
    """
    if not isinstance(text, str):
        return ""
    text = text.replace("..", ".") # replace double dots with single dot
    text = text.replace(",", "")  # replace commas with nothing
    text = re.sub(r'\s+', ' ', text)  # replace multiple spaces with a single space
    text = text.strip().strip('.') # remove dots in the beginning and end
    text = re.sub(r"[\[\]\(\)\{\}]", "", text) # remove brackets
    text = re.sub(r"^\d+\s*", "", text)  # remove numbers only at the start
    text = text.replace("","")  # remove numbers only at the start
    text = re.sub(r'\b(\d)(SG|PL)\b', r'\1.\2', text)

    return text.strip() 


def gloss_to_ud_features(gloss: str) -> list[str]:
    if not isinstance(gloss, str):
        return []

    per_token_feats: list[str] = []
    for token in gloss.split():
        # decide if this token actually has gloss codes
        is_gloss = ("." in token or token.isupper() or any(char.isdigit() for char in token))
        if not is_gloss:
            per_token_feats.append("") 
            TOKEN_WITHOUT_GLOSS.add(token)
            continue

        feats: list[str] = []
        codes = [c.upper() for c in token.split(".")]
        # strip off any lowercase “lemma” prefix
        if codes and codes[0].islower():
            codes.pop(0)

        for code in codes:
            ud_pair = LEIPZIG2UD.get(code)
            if ud_pair:
                feat_name, feat_val = ud_pair
                feats.append(f"{feat_name}={feat_val}")
            else:
                UNKNOWN_CODES.add(code)

        # join with "|" or use empty string if nothing mapped
        per_token_feats.append("|".join(feats) if feats else "")

    return per_token_feats


def build_docbin(lang: str, study: str, input_dir: str, pretrained_model : Language = None) -> DocBin:
    log_path = Path(input_dir) / "glossing_traindata.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    fh = setup_file_logger(str(log_path))
    if not logger.hasHandlers():
        logger.addHandler(fh)

    # 1. Load spacy model
    if not pretrained_model:
        if lang == "de":
            pretrained_model = "de_core_news_lg"
        elif lang == "en":
            pretrained_model = "en_core_web_lg"

    if pretrained_model:
        nlp = spacy.load(pretrained_model)
        logger.info(f"Loaded pretrained model: {pretrained_model}")
    else:
        nlp = spacy.blank(lang)
        logger.info(f"Loaded blank model for language: {lang}")

    docbin = DocBin(attrs=["MORPH"], store_user_data=True)
    all_examples = []

    for root, dirs, files in os.walk(input_dir):
        for fname in files:
            if not fname.endswith("annotated.xlsx"):
                continue

            try:
                # 2. For each file, initialize helper lists
                cleaned_texts = []
                cleaned_glosses = []
                valid_texts = []
                valid_glosses = []

                # 3. Read the file and process the texts and glosses
                file_path = os.path.join(root, fname)
                df = pd.read_excel(file_path, nrows=60)
                df = df.dropna(subset=[TEXT_COLUMN, GLOSS_COLUMN])

                raw_texts = df[TEXT_COLUMN].astype(str).tolist()
                raw_glosses = df[GLOSS_COLUMN].astype(str).tolist()

                #4. get raw texts and glosses, clean them, and check for mismatches
                for t in raw_texts:
                    t_clean = clean_text(t)
                    lines = [line.strip() for line in t_clean.split("\n") if line.strip()]
                    cleaned_texts.extend(lines)

                for g in raw_glosses:
                    g_clean = clean_text(g)
                    gloss_lines = [line.strip() for line in g_clean.split("\n") if line.strip()]
                    cleaned_glosses.extend(gloss_lines)

                #4.1 check if cleaned texts and glosses match. Else skip the file
                if len(cleaned_texts) != len(cleaned_glosses):
                    msg.warn(
                        f"Mismatch in lengths: {len(cleaned_texts)} texts vs "
                        f"{len(cleaned_glosses)} glosses in file {file_path}"
                    )
                    msg.warn("Skipping this file due to mismatch.")
                    logger.warning(f"Mismatch in lengths: {len(cleaned_texts)} texts vs {len(cleaned_glosses)} glosses in file {file_path}")
                    continue
                else:
                    msg.good(f"Matched {len(cleaned_texts)} texts with {len(cleaned_glosses)} glosses in file {file_path}")
                    logger.info(f"Matched {len(cleaned_texts)} texts with {len(cleaned_glosses)} glosses in file {file_path}")
                
                #5. Check if texts and glosses have the same number of tokens
                for i, (text, gloss) in enumerate(zip(cleaned_texts, cleaned_glosses)):
                    tokens = text.split()
                    glosses = gloss.split()
                    if len(tokens) != len(glosses):
                        msg.warn(
                            f"Token mismatch at pair {i}: "
                            f"{tokens} vs {glosses}"
                            f"{len(tokens)} tokens in text vs {len(glosses)} in gloss — skipping."
                        )
                        logger.warning(
                            f"Token mismatch at pair {i}: "
                            f"{tokens} vs {glosses}"
                            f"{len(tokens)} tokens in text vs {len(glosses)} in gloss — skipping."
                        )
                    else:
                        valid_texts.append(text)
                        valid_glosses.append(gloss)
                
                #6. Process valid texts and glosses
                if not valid_texts or not valid_glosses:
                    msg.warn(f"No valid text-gloss pairs found in file {file_path}. Skipping.")
                    logger.warning(f"No valid text-gloss pairs found in file {file_path}. Skipping.")
                    continue

                msg.good(f"Processing {len(valid_glosses)} text-gloss pairs from {file_path}")
                logger.info(f"Processing {len(valid_glosses)} text-gloss pairs from {file_path}")
                feats_list = [gloss_to_ud_features(g) for g in valid_glosses]

                for text, feats in zip(valid_texts, feats_list):
                    doc = nlp(text)
                    for token, feat in zip(doc, feats):
                        token.set_morph(feat)
                    docbin.add(doc)
                    all_examples.append({"text": text, "gloss": " ".join(feats)})
            
            except Exception as e:
                msg.fail(f"Error processing file {file_path}: {e}")
                logger.error(f"Error processing file {file_path}: {e}")
                continue

    if all_examples:
        pd.DataFrame(all_examples).to_excel(f"training/data/{lang}_{study}_train_spacy.xlsx", index=False)

    save_path = SCRIPT_PATH / "data" / f"{lang}_{study}_train.spacy"
    docbin.to_disk(save_path)
    msg.good(f"Built DocBin with {len(docbin)} documents from {input_dir}")
    logger.info(f"Built DocBin with {len(docbin)} documents from {input_dir}")

    if TOKEN_WITHOUT_GLOSS:
        msg.warn(f"Tokens without gloss: {len(TOKEN_WITHOUT_GLOSS)}: {TOKEN_WITHOUT_GLOSS}")
        logger.warning(f"Tokens without gloss: {TOKEN_WITHOUT_GLOSS}")
    if UNKNOWN_CODES:
        msg.warn(f"Unknown codes: {len(UNKNOWN_CODES)}: {UNKNOWN_CODES}")
        logger.warning(f"Unknown codes: {UNKNOWN_CODES}")
    
    config = util.load_config(BASE_CONFIG_PATH)
    config["nlp"]["lang"] = lang
    config["paths"]["train"] = str(save_path)
    config["paths"]["dev"] = str(save_path)
    if pretrained_model:
        config["paths"]["vectors"] = pretrained_model

    config.to_disk("training/glossing/configs/config.cfg")

    fill_config(
        base_path=Path("training/glossing/configs/config.cfg"),
        output_file=Path("training/glossing/configs/config.cfg"),
    )

    debug_data("training/glossing/configs/config.cfg", silent=False, verbose=True, no_format=False)

    logger.removeHandler(fh)
    fh.close()

def build_translationset(lang: str, study: str, input_dir: str) -> None:
    log_path = Path(input_dir) / "translation_traindata.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    fh = setup_file_logger(str(log_path))
    if not logger.hasHandlers():
        logger.addHandler(fh)

    records = []  # will hold both sentence‐ and token‐level rows

    for root, dirs, files in os.walk(input_dir):
        for fname in files:
            if not fname.endswith("annotated.xlsx"):
                continue
            file_path = Path(root) / fname
            try:
                df = pd.read_excel(file_path)
                df = df.dropna(subset=[TEXT_COLUMN, GLOSS_COLUMN, TRANSLATION_COLUMN])

                lower_and_clean = lambda x: (
                    x.lower()
                    .replace("‘", "")
                    .replace("’", "")
                    .replace("'", "")
                    .strip()
                )

                # 1) clean each column
                texts        = df[TEXT_COLUMN].astype(str).map(clean_text).map(lower_and_clean).tolist()
                translations = df[TRANSLATION_COLUMN].astype(str).map(clean_text).map(lower_and_clean).tolist()
                glosses      = df[GLOSS_COLUMN].astype(str).map(clean_text).tolist()
                

                # 2) require same number of sentences
                if not (len(texts) == len(glosses) == len(translations)):
                    msg.warn(
                        f"Line count mismatch in {file_path}: "
                        f"{len(texts)} texts, {len(glosses)} glosses, {len(translations)} translations — skipping file"
                    )
                    logger.warning(f"Line count mismatch in {file_path}")
                    continue

                # 3) per‐sentence alignment
                for i, (sent, gloss_line, full_tr) in enumerate(zip(texts, glosses, translations)):
                    t_tokens = sent.split()
                    g_tokens = gloss_line.split()

                    if len(t_tokens) != len(g_tokens):
                        msg.warn(
                            f"Token count mismatch in {file_path} line {i}: "
                            f"{len(t_tokens)} text vs {len(g_tokens)} gloss — skipping line"
                        )
                        logger.warning(f"Token count mismatch in {file_path} line {i}")
                        continue

                    # — sentence‐level record —
                    records.append({
                        "unit_type":  "sentence",
                        "text":       sent,
                        "translation": full_tr,
                    })

                    # — token‐level records —
                    for tok, gloss_tok in zip(t_tokens, g_tokens):
                        head = gloss_tok.split(".")[0]
                        if head.islower():
                            records.append({
                                "unit_type":  "token",
                                "text":       tok,
                                "translation": head,
                            })

            except Exception as e:
                msg.fail(f"Error in {file_path}: {e}")
                logger.error(f"Skipping {file_path} due to {e}")

    # 4) dump to one big Excel
    if records:
        out_dir = Path("training/data")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{lang}_{study}_train_translation.xlsx"
        pd.DataFrame(records).to_excel(out_path, index=False)
        msg.good(f"Wrote {len(records)} rows (sentence + token) to {out_path}")
        logger.info(f"Wrote {len(records)} rows to {out_path}")
    else:
        msg.warn("No records generated.")
        logger.warning("No records generated.")

    logger.removeHandler(fh)
    fh.close()




if __name__ == '__main__':
    lang= "yo"
    study = "H"
    input_dir = "C:/Users/camelo.cruz/Leibniz-ZAS/Leibniz Dream Data - Studies/H_Dependencies/H06a-Relative-Clause-Production-study/H06a_raw_files_yor/H06a_raw_files_yor_adults/data_1732047553925"
    #build_docbin(lang, study, input_dir= input_dir, pretrained_model= None)
    build_translationset(lang, study, input_dir)
