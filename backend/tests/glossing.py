import os
from pathlib import Path
import re
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.metrics import precision_recall_fscore_support, accuracy_score, hamming_loss
import pandas as pd
import matplotlib.pyplot as plt


def clean_text(text: str) -> str:
    text = re.sub(r'^[^A-Za-z0-9]+|[^A-Za-z0-9.]+$', '', text)
    if '.' in text:
        before, after = text.split('.', 1)
        if before.islower():
            return after
        return text.strip('.')
    if text.isupper():
        return text
    return ''

def extract_atomic_from_gloss(gloss: str) -> set[str]:
    return set(gloss.split('.')) if gloss else set()


def process_dir(dir_path: str, gloss_col: str, gold_col: str):
    per_atom_records = []

    for root, _, files in os.walk(dir_path):
        for fname in files:
            if not fname.endswith("annotated.xlsx"):
                continue

            df = pd.read_excel(os.path.join(root, fname))

            if gloss_col not in df.columns or gold_col not in df.columns:
                print(f" → missing expected columns in {fname}, skipping")
                continue

            for _, row in df.iterrows():
                preds_lines = [ln.split() for ln in str(row[gloss_col]).split('\n') if ln]
                golds_lines = [ln.split() for ln in str(row[gold_col]).split('\n') if ln]

                # for each sentence
                for p_raw, g_raw in zip(preds_lines, golds_lines):
                    # build per-token atomic sets
                    p_sets = [
                        extract_atomic_from_gloss(clean_text(tok))
                        for tok in p_raw if clean_text(tok)
                    ]
                    g_sets = [
                        extract_atomic_from_gloss(clean_text(tok))
                        for tok in g_raw if clean_text(tok)
                    ]

                    # now iterate per token, not merging across the sentence
                    for p_atoms, g_atoms in zip(p_sets, g_sets):
                        # for each atomic feature in this token
                        for atomic in sorted(p_atoms | g_atoms):
                            per_atom_records.append({
                                'gold':  g_atoms,
                                'pred':  p_atoms
                            })

    df_atoms = pd.DataFrame(per_atom_records)
    current_dir = Path(__file__).resolve().parent
    df_atoms.to_csv(current_dir / 'per_atom_records.csv', index=False)
    return df_atoms


def compute_per_label_report(df_atoms: pd.DataFrame) -> pd.DataFrame:
    """
    Compute precision, recall, f1-score, and support for each atomic feature label.

    Args:
        df_atoms: DataFrame with two columns 'gold' and 'pred', each a set of labels per token.

    Returns:
        DataFrame with metrics for each label.
    """
    mlb = MultiLabelBinarizer()
    y_true = mlb.fit_transform(df_atoms['gold'])
    y_pred = mlb.transform(df_atoms['pred'])

    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true,
        y_pred,
        zero_division=0,
        average=None
    )
    support = y_true.sum(axis=0)

    report_df = pd.DataFrame(
        {
            'precision': precision,
            'recall': recall,
            'f1-score': f1,
            'support': support
        },
        index=mlb.classes_
    )
    return report_df


def plot_metrics(report_df: pd.DataFrame):
    """
    Create an enhanced, clean bar chart of precision, recall, and F1-score per label.

    If save_path is provided, saves the figure to that path.
    """
    labels = list(report_df.index)
    x = range(len(labels))
    width = 0.25

    p = report_df['precision'].values
    r = report_df['recall'].values
    f = report_df['f1-score'].values

    plt.figure(figsize=(12, 8))
    # Bars
    bars_p = plt.bar([i - width for i in x], p, width, label='Precision', edgecolor='black')
    bars_r = plt.bar(x, r, width, label='Recall', edgecolor='black')
    bars_f = plt.bar([i + width for i in x], f, width, label='F1-score', edgecolor='black')

    # Add value labels above each bar
    for bars in (bars_p, bars_r, bars_f):
        for bar in bars:
            height = bar.get_height()
            plt.annotate(f'{height:.2f}',
                         xy=(bar.get_x() + bar.get_width() / 2, height),
                         xytext=(0, 3),
                         textcoords='offset points',
                         ha='center', va='bottom', fontsize=10)

    # Layout adjustments
    plt.xticks(x, labels, rotation=45, ha='right', fontsize=12)
    plt.yticks(fontsize=12)
    plt.ylabel('Score', fontsize=14)
    plt.title('Per-Atomic-Feature Classification Metrics', fontsize=16, pad=15)
    plt.grid(axis='y', linestyle='--', linewidth=0.7, alpha=0.7)
    plt.legend(fontsize=12)
    plt.tight_layout()

    save_path = Path(__file__).resolve().parent / 'per_atomic_feature_metrics.png'
    plt.savefig(save_path, dpi=300)



if __name__ == '__main__':
    DATA_DIR = '/Users/alejandra/Library/CloudStorage/OneDrive-FreigegebeneBibliotheken–Leibniz-ZAS/Leibniz Dream Data - Studies/tests_alejandra/yoruba/to_test'
    GLOSS_COL = 'automatic_glossing'
    GOLD_COL  = 'glossing_utterance_used'

    # 1) Build one row PER TOKEN-PER ATOMIC FEATURE
    df_atoms = process_dir(DATA_DIR, GLOSS_COL, GOLD_COL)

    # 2) Compute per-label metrics
    report_df = compute_per_label_report(df_atoms)
    print("\nPer‑atomic‑feature classification report:\n")
    print(report_df.round(3))

    # 3) Plot metrics
    plot_metrics(report_df)

    # 4) Overall multilabel metrics
    mlb = MultiLabelBinarizer()
    y_true = mlb.fit_transform(df_atoms['gold'])
    y_pred = mlb.transform(df_atoms['pred'])

    overall_acc = accuracy_score(y_true, y_pred)
    overall_hl  = hamming_loss(y_true, y_pred)
    print(f"\nOverall subset accuracy: {overall_acc:.3f}")
    print(f"Overall hamming_loss:    {overall_hl:.3f}")
