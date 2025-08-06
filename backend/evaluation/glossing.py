import os
import re
import argparse
from pathlib import Path
from typing import Set, List

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.metrics import (
    precision_recall_fscore_support,
    accuracy_score,
    hamming_loss
)


def clean_text(text: str) -> str:
    """
    Remove bracketed content, leading/trailing non-alphanumeric (except dot),
    and normalize hyphenated tokens.
    """
    # Remove any text in parentheses or brackets
    text = re.sub(r"[\(\[][^()\[\]]*[\)\]]", "", text)
    # Strip non-alphanumeric (and non-dot) from the ends
    text = re.sub(r"^[^A-Za-z0-9]+|[^A-Za-z0-9.]+$", "", text)
    # Handle hyphens: drop leading lowercase prefixes
    if '-' in text:
        before, after = text.split('-', 1)
        if before.islower():
            return after
        return text.strip('-')
    # Keep all-uppercase tokens
    if text.isupper():
        return text
    # Otherwise drop
    return ''


def extract_atomic_from_gloss(gloss: str) -> Set[str]:
    """
    Split a gloss string on hyphens into atomic features.
    """
    return set(gloss.split('-')) if gloss else set()


def process_dir(
    dir_path: str,
    gloss_col: str,
    gold_col: str
) -> pd.DataFrame:
    """
    Walk `dir_path` for '*annotated.xlsx' files, extract per-token atomic features,
    and build a DataFrame with columns 'gold' and 'pred' containing sets of labels.
    """
    records = []
    for root, _, files in os.walk(dir_path):
        for fname in files:
            if not fname.endswith('annotated.xlsx'):
                continue
            path = os.path.join(root, fname)
            df = pd.read_excel(path)
            if gloss_col not in df.columns or gold_col not in df.columns:
                print(f"→ skipping {fname}: missing columns {gloss_col} or {gold_col}")
                continue
            print(f"→ processing {fname}...")
            for _, row in df.iterrows():
                preds_lines = [ln.split() for ln in str(row[gloss_col]).split('\n') if ln]
                golds_lines = [ln.split() for ln in str(row[gold_col]).split('\n') if ln]
                for p_raw, g_raw in zip(preds_lines, golds_lines):
                    p_sets = [extract_atomic_from_gloss(clean_text(tok)) for tok in p_raw if clean_text(tok)]
                    g_sets = [extract_atomic_from_gloss(clean_text(tok)) for tok in g_raw if clean_text(tok)]
                    for p_atoms, g_atoms in zip(p_sets, g_sets):
                        union = sorted(p_atoms | g_atoms)
                        if not union:
                            records.append({'gold': set(), 'pred': set()})
                        else:
                            for _ in union:
                                records.append({'gold': g_atoms, 'pred': p_atoms})
    df_atoms = pd.DataFrame(records)
    print(f"Built per-atom DataFrame: {df_atoms.shape[0]} rows")
    return df_atoms


def compute_per_label_report(df_atoms: pd.DataFrame) -> pd.DataFrame:
    """
    Compute precision, recall, f1-score, and support per atomic feature.
    """
    mlb = MultiLabelBinarizer()
    y_true = mlb.fit_transform(df_atoms['gold'])
    y_pred = mlb.transform(df_atoms['pred'])
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, zero_division=0, average=None
    )
    support = y_true.sum(axis=0)
    return pd.DataFrame(
        {
            'precision': precision,
            'recall': recall,
            'f1-score': f1,
            'support': support
        },
        index=mlb.classes_
    )


def compute_label_confusion(df_atoms: pd.DataFrame) -> pd.DataFrame:
    """
    Build an (N+1)x(N+1) confusion matrix over atomic labels, including 'Ø'.
    """
    mlb = MultiLabelBinarizer()
    y_true = mlb.fit_transform(df_atoms['gold'])
    y_pred = mlb.transform(df_atoms['pred'])
    labels = list(mlb.classes_)
    NONE = 'Ø'
    # initialize
    conf = pd.DataFrame(
        0,
        index=labels + [NONE],
        columns=labels + [NONE],
        dtype=int
    )
    idx2lab = {i: lab for i, lab in enumerate(labels)}
    for t_vec, p_vec in zip(y_true, y_pred):
        true_idx = set(np.where(t_vec)[0])
        pred_idx = set(np.where(p_vec)[0])
        tp = true_idx & pred_idx
        fn = true_idx - pred_idx
        fp = pred_idx - true_idx
        # TP
        for i in tp:
            conf.at[idx2lab[i], idx2lab[i]] += 1
        # FN -> gold i missed
        for i in fn:
            conf.at[idx2lab[i], NONE] += 1
        # FP -> pred j spuriously
        for j in fp:
            conf.at[NONE, idx2lab[j]] += 1
        # Confusions FN x FP
        for i in fn:
            for j in fp:
                conf.at[idx2lab[i], idx2lab[j]] += 1
    return conf


def plot_label_confusion(conf: pd.DataFrame, language: str):
    """
    Plot the cross-label confusion matrix including 'Ø'.
    """
    labels = list(conf.index)
    size = max(7, len(labels) * 0.6)
    fig, ax = plt.subplots(figsize=(size, size))
    im = ax.imshow(conf.values, interpolation='nearest', cmap='Blues')
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha='right')
    ax.set_yticklabels(labels)
    vmax = conf.values.max()
    for i in range(len(labels)):
        for j in range(len(labels)):
            color = 'white' if conf.iat[i,j] > vmax * 0.7 else 'black'
            ax.text(j, i, conf.iat[i,j], ha='center', va='center', fontsize=7, color=color)
    ax.set_xlabel('Predicted')
    ax.set_ylabel('Gold')
    ax.set_title('Atomic Label Confusion Matrix (Ø = none)')
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    plt.tight_layout()
    out = Path(__file__).parent / f"{language}_label_confusion_matrix.png"
    plt.savefig(out, dpi=300)
    plt.close(fig)
    print(f"Saved confusion matrix to {out}")


def main():
    parser = argparse.ArgumentParser(
        description='Evaluate atomic glossing predictions.'
    )
    parser.add_argument('data_dir', help='Root directory of annotated Excel files')
    parser.add_argument('--gloss-col', default='automatic_glossing', help='Predicted gloss column')
    parser.add_argument('--gold-col',  default='gold_glossing',      help='Gold gloss column')
    parser.add_argument('--lang',      default='yo',                  help='Language code for outputs')
    args = parser.parse_args()

    df_atoms = process_dir(args.data_dir, args.gloss_col, args.gold_col)

    # Per-atomic label report
    report_df = compute_per_label_report(df_atoms)
    print("\nPer-atomic-feature classification report:\n")
    print(report_df.round(3))

    # Cross-label confusion
    conf_df = compute_label_confusion(df_atoms)
    plot_label_confusion(conf_df, args.lang)

    # Overall metrics
    mlb = MultiLabelBinarizer()
    y_true = mlb.fit_transform(df_atoms['gold'])
    y_pred = mlb.transform(df_atoms['pred'])
    acc = accuracy_score(y_true, y_pred)
    prec, rec, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average='macro', zero_division=0
    )
    hl = hamming_loss(y_true, y_pred)
    print(f"\nOverall accuracy:        {acc:.3f}")
    print(f"Overall precision:       {prec:.3f}")
    print(f"Overall recall:          {rec:.3f}")
    print(f"Overall F1-score:        {f1:.3f}")
    print(f"Overall hamming_loss:    {hl:.3f}")


if __name__ == '__main__':
    main()
