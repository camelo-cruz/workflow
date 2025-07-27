import os
from pathlib import Path
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    hamming_loss,
    classification_report
)
from sklearn.preprocessing import MultiLabelBinarizer
import pandas as pd
import re
import matplotlib.pyplot as plt


def clean_text(text: str) -> str:
    """
    Cleans a single gloss token:
    - Trims non-alphanumeric/dot at boundaries.
    - Splits on first dot: drops lowercase prefix, else strips dots.
    - Returns uppercase tokens as-is if fully uppercase.
    - Returns empty if not a valid gloss.
    """
    text = re.sub(r'^[^A-Za-z0-9]+|[^A-Za-z0-9.]+$', '', text)
    if '.' in text:
        before, after = text.split('.', 1)
        if before.islower():
            return after
        return text.strip('.')
    if text.isupper():
        return text
    return ''


def normalize_gloss(gloss: str) -> str:
    """
    Sorts the internal components of a gloss (e.g., 'TNS.3.SG' -> '3.SG.TNS').
    """
    parts = gloss.split('.')
    return '.'.join(sorted(parts))


def extract_atomic(gloss_list: list[str]) -> set[str]:
    """
    From a list of normalized gloss strings, extract atomic features.
    """
    atoms = set()
    for gloss in gloss_list:
        atoms.update(gloss.split('.'))
    return atoms


def process_dir(dir: str, language, study):
    """
    Processes a DataFrame with 'automatic_glossing' and 'glossing_utterance_used' columns.
    Returns the exploded DataFrame, computed metrics, and classification report.
    """
    glossing_col = 'automatic_glossing'
    golden_col = 'glossing_utterance_used'

    records = []
    for root, _, files in os.walk(dir):
        for f in files:
            if f.endswith("annotated.xlsx"):
                df = pd.read_excel(os.path.join(root, f))
                for _, row in df.iterrows():
                    preds_lines = [line.split() for line in str(row[glossing_col]).split('\n') if line]
                    golds_lines = [line.split() for line in str(row[golden_col]).split('\n') if line]
                    for p_raw, g_raw in zip(preds_lines, golds_lines):
                        p_norm = sorted({
                            normalize_gloss(tok)
                            for tok in (clean_text(token) for token in p_raw) if tok
                        })
                        g_norm = sorted({
                            normalize_gloss(tok)
                            for tok in (clean_text(token) for token in g_raw) if tok
                        })
                        if not p_norm and not g_norm:
                            continue
                        p_atoms = extract_atomic(p_norm)
                        g_atoms = extract_atomic(g_norm)
                        records.append({glossing_col: p_atoms, golden_col: g_atoms})

    exploded = pd.DataFrame(records)
    current_dir = Path(__file__).parent
    save_path = os.path.join(current_dir, f'exploded_glosses_{language}_{study}.csv')
    print(f"Saving exploded glosses to {save_path}")
    exploded.to_csv(save_path, index=False)

    # Binarize atomic labels
    mlb = MultiLabelBinarizer()
    y_true = mlb.fit_transform(exploded[golden_col])
    y_pred = mlb.transform(exploded[glossing_col])
    label_names = mlb.classes_

    # Compute metrics
    metrics = {
        'subset_accuracy': accuracy_score(y_true, y_pred),
        'hamming_loss': hamming_loss(y_true, y_pred)
    }
    p_macro, r_macro, f_macro, _ = precision_recall_fscore_support(
        y_true, y_pred, average='macro', zero_division=0
    )
    metrics.update({
        'precision_macro': p_macro,
        'recall_macro': r_macro,
        'f1_macro': f_macro
    })
    p_w, r_w, f_w, _ = precision_recall_fscore_support(
        y_true, y_pred, average='weighted', zero_division=0
    )
    metrics.update({
        'precision_weighted': p_w,
        'recall_weighted': r_w,
        'f1_weighted': f_w
    })

    # Per-label report
    report = classification_report(
        y_true, y_pred, target_names=label_names, zero_division=0
    )

    return exploded, metrics, report


def plot_metrics(metrics: dict, save_path: str) -> None:
    """
    Plots bar chart of metrics and saves to the given path.
    """
    labels = list(metrics.keys())
    values = [metrics[k] for k in labels]

    plt.figure()
    plt.bar(labels, values)
    plt.title('Atomic Feature Performance Metrics')
    plt.xlabel('Metric')
    plt.ylabel('Score')
    plt.ylim(0, 1)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    plt.savefig(save_path)
    plt.close()


def main(data_dir: str, language: str, instruction: str, study: str):
    """
    Example main function to process gloss data and plot metrics.
    """
    # Load your DataFrame here, e.g. from CSV or other source
    data_dir = Path(data_dir)
    exploded, metrics, report = process_dir(dir=data_dir, language=language, study=study)

    print("Computed metrics:")
    for k, v in metrics.items():
        print(f"  {k}: {v:.3f}")
    print("Per-atomic-feature classification report:")
    print(report)

    save_path = Path(data_dir) / f"metrics_{language}_{study}.png"
    plot_metrics(metrics, str(save_path))


if __name__ == '__main__':
    main(
        '/Users/alejandra/Library/CloudStorage/OneDrive-FreigegebeneBibliotheken–Leibniz-ZAS/Leibniz Dream Data - Studies/tests_alejandra/yoruba/Session_1236640',
        language='yo',
        instruction='glossing',
        study='H'
    )
