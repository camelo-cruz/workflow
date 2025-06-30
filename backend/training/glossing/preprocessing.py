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

SCRIPT_PATH = Path(__file__).parent
PARENT_PATH = SCRIPT_PATH.parent
BASE_CONFIG_PATH = SCRIPT_PATH / "base_config.cfg"

TEXT_COLUMN = "latin_transcription_utterance_used"
GLOSS_COLUMN = "glossing_utterance_used"

# Load mapping resources
LEIPZIG_GLOSSARY = load_glossing_rules("LEIPZIG_GLOSSARY.json")
SPACY2CATEGORY = load_glossing_rules("VALUE2FEATURE.json")
LEIPZIG2SPACY = {v: k for k, v in LEIPZIG_GLOSSARY.items()}

TOKEN_WITHOUT_GLOSS: set[str] = set() # Initialize set to store tokens without gloss
UNKNOWN_CODES: set[str] = set() # Initialize set to store unknown codes. This means that the code is not in our list of LEIPZIG_GLOSSARY and needs to be added

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def setup_file_logger(log_path: str) -> logging.FileHandler:
    fh = logging.FileHandler(log_path)
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
    text = re.sub(r"\d+", "", text)  # remove numbers
    text = re.sub(r"[\[\]\(\)\{\}]", "", text) # remove brackets
    text = text.replace("..", ".") # replace double dots with single dot
    text = text.replace(",", "")  # replace commas with nothing
    text = text.strip().strip('.') # remove dots in the beginning and end
    return text.strip() 


def gloss_to_ud_features(gloss: str) -> list[str]:
    if not isinstance(gloss, str):
        return []

    per_token_feats: list[str] = [] # Initialize list to store features for each token
    for token in gloss.split():
        # Case 1: no “.” ⇒ not glossed because . means that the token has a gloss
        if "." not in token:
            per_token_feats.append('') # Why am I doing this? In spacy is nothing. Dict in morph.dict is empty
            TOKEN_WITHOUT_GLOSS.add(token)
            continue

        # Case 2: has gloss, map each code
        else:
            codes = [c.upper() for c in token.split(".")[1:]]  # Convert codes to uppercase
            feats: list[str] = []
            for code in codes:
                spacy_value = LEIPZIG2SPACY.get(code)
                feat_name   = SPACY2CATEGORY.get(spacy_value)
                if spacy_value and feat_name:
                    feats.append(f"{feat_name}={spacy_value}")
                else:
                    UNKNOWN_CODES.add(code)  # Add unknown code to the set

            # If no features mapped, use “_” as placeholder
            per_token_feats.append("|".join(feats) if feats else '') # Which placeholder to use?

    return per_token_feats


def build_docbin(lang: str, input_dir: str, pretrained_model : Language = None) -> DocBin:
    # 1. Load spacy model
    if pretrained_model:
        nlp = spacy.load(pretrained_model)
    else:
        nlp = spacy.blank(lang)

    docbin = DocBin(attrs=["MORPH"], store_user_data=True)
    all_examples = []

    for root, dirs, files in os.walk(input_dir):
        for fname in files:
            if not fname.endswith("annotated.xlsx"):
                continue

            log_path = f"{root}/traindata.log"
            fh = setup_file_logger(log_path)

            if not any(isinstance(h, logging.FileHandler) and h.baseFilename == fh.baseFilename for h in logger.handlers):
                logger.addHandler(fh)
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
                    logger.info(f"Processing {len(cleaned_texts)} texts and glosses from {file_path}")
                
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
                
                logger.removeHandler(fh)
                fh.close()
            except Exception as e:
                msg.fail(f"Error processing file {file_path}: {e}")
                logger.error(f"Error processing file {file_path}: {e}")
                continue
            finally:
                logger.removeHandler(fh)
                fh.close()

    if all_examples:
        pd.DataFrame(all_examples).to_excel("training/glossing/data/train.xlsx", index=False)

    msg.good(f"Built DocBin with {len(docbin)} documents from {input_dir}")
    print("Total examples:", len(list(docbin.get_docs(nlp.vocab))))
    if TOKEN_WITHOUT_GLOSS:
        msg.warn(f"Tokens without gloss: {len(TOKEN_WITHOUT_GLOSS)}")
        logger.warning(f"Tokens without gloss: {TOKEN_WITHOUT_GLOSS}")
    if UNKNOWN_CODES:
        msg.warn(f"Unknown codes: {len(UNKNOWN_CODES)}")
        logger.warning(f"Unknown codes: {UNKNOWN_CODES}")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        temp_docbin_path = tmpdir / "train.spacy"
        docbin.to_disk(temp_docbin_path)

        config = util.load_config(BASE_CONFIG_PATH)
        config["nlp"]["lang"] = lang
        config["paths"]["train"] = str(temp_docbin_path)
        config["paths"]["dev"] = str(temp_docbin_path)

        config.to_disk(tmpdir / "config.cfg")

        fill_config(
        base_path=tmpdir / "config.cfg",
        output_file=tmpdir / "config.cfg",
        )

        debug_data(tmpdir / "config.cfg", silent=False, verbose=True)

    save_path = SCRIPT_PATH / "data" / f"{lang}_train.spacy"
    docbin.to_disk(save_path)
    msg.good(f"Saved DocBin to {save_path}")


if __name__ == '__main__':
    build_docbin("de", input_dir='/Users/alejandra/Library/CloudStorage/OneDrive-FreigegebeneBibliotheken–Leibniz-ZAS/Leibniz Dream Data - Studies/F_Negative_Concepts/F07a-Comparatives/F07a_deu',
                 pretrained_model="de_core_news_lg")
