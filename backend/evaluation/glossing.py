import os
from pathlib import Path
import re
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.metrics import precision_recall_fscore_support, accuracy_score, hamming_loss
import pandas as pd
import matplotlib.pyplot as plt
import math
from sklearn.metrics import multilabel_confusion_matrix



def clean_text(text: str) -> str:
    text = re.sub(r'[\(\[][^()\[\]]*[\)\]]', '', text)

    # Remove non-alphanumeric characters from the start and end
    text = re.sub(r'^[^A-Za-z0-9]+|[^A-Za-z0-9.]+$', '', text)
    if '-' in text:
        before, after = text.split('-', 1)
        if before.islower():
            return after
        return text.strip('-')
    if text.isupper():
        return text
    return ''

def extract_atomic_from_gloss(gloss: str) -> set[str]:
    return set(gloss.split('-')) if gloss else set()


def process_dir(dir_path: str, gloss_col: str, gold_col: str, language: str):
    per_atom_records = []

    for root, _, files in os.walk(dir_path):
        for fname in files:
            if not fname.endswith("annotated.xlsx"):
                continue

            path = os.path.join(root, fname)
            df = pd.read_excel(path)

            if gloss_col not in df.columns or gold_col not in df.columns:
                print(f" → missing expected columns in {fname} in {root}, skipping")
                continue
            else:
                print(f" → processing {fname}...")

            for i, row in df.iterrows():
                preds_lines = [ln.split() for ln in str(row[gloss_col]).split('\n') if ln]
                golds_lines = [ln.split() for ln in str(row[gold_col]).split('\n') if ln]
                
                # for each sentence pair (stop at min length)
                for p_raw, g_raw in zip(preds_lines, golds_lines):
                    p_sets = [
                        extract_atomic_from_gloss(clean_text(tok))
                        for tok in p_raw if clean_text(tok)
                    ]
                    g_sets = [
                        extract_atomic_from_gloss(clean_text(tok))
                        for tok in g_raw if clean_text(tok)
                    ]

                    # iterate per token up to min length
                    for p_atoms, g_atoms in zip(p_sets, g_sets):
                        union_atoms = sorted(p_atoms | g_atoms)
                        if not union_atoms:
                            # still record empty case if you want, or skip with debug
                            per_atom_records.append({'gold': set(), 'pred': set()})
                            continue
                        for atomic in union_atoms:
                            per_atom_records.append({
                                'gold': g_atoms,
                                'pred': p_atoms
                            })

    df_atoms = pd.DataFrame(per_atom_records)

    # Debug info
    print(f"[{language}] Built per-atom DataFrame with shape {df_atoms.shape}")
    if 'gold' not in df_atoms.columns or 'pred' not in df_atoms.columns:
        print(f"WARNING: expected columns missing: {df_atoms.columns.tolist()}")
    else:
        print(f"Example rows:\n{df_atoms.head(5)}")

    current_dir = Path(__file__).resolve().parent
    df_atoms.to_csv(current_dir / f'{language}_per_atom_records.csv', index=False)
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



def plot_confusion_matrices(df_atoms: pd.DataFrame, language: str):
    """
    Compute and plot a 2×2 confusion matrix (TN, FP, FN, TP)
    for each atomic feature label in a grid of heatmaps.
    """
    # Binarize the multilabel data
    mlb = MultiLabelBinarizer()
    y_true = mlb.fit_transform(df_atoms['gold'])
    y_pred = mlb.transform(df_atoms['pred'])

    labels = mlb.classes_
    # Get one confusion matrix per label
    cms = multilabel_confusion_matrix(y_true, y_pred)

    n_labels = len(labels)
    cols = 3  # you can tweak this
    rows = math.ceil(n_labels / cols)

    fig, axes = plt.subplots(rows, cols, figsize=(cols * 4, rows * 4))
    axes = axes.flatten()

    for idx, (cm, label) in enumerate(zip(cms, labels)):
        ax = axes[idx]
        im = ax.imshow(cm, interpolation='nearest', cmap='Blues')
        ax.set_title(label, fontsize=12)
        ax.set_xticks([0, 1])
        ax.set_xticklabels(['Pred 0', 'Pred 1'])
        ax.set_yticks([0, 1])
        ax.set_yticklabels(['True 0', 'True 1'])

        # Annotate counts
        for i in (0, 1):
            for j in (0, 1):
                ax.text(j, i, cm[i, j],
                        ha='center', va='center', fontsize=10)

    # Turn off any extra subplots
    for j in range(idx + 1, len(axes)):
        axes[j].axis('off')

    plt.tight_layout()
    save_path = Path(__file__).resolve().parent / f'{language}_confusion_matrices.png'
    plt.savefig(save_path, dpi=300)
    plt.close(fig)


if __name__ == '__main__':
    DATA_DIR = '/Users/alejandra/Library/CloudStorage/OneDrive-FreigegebeneBibliotheken–Leibniz-ZAS/Leibniz Dream Data - Studies/tests_alejandra/tesis_data/yoruba/to_test'
    GLOSS_COL = 'automatic_glossing'
    GOLD_COL  = 'gold_glossing'
    LANGUAGE = 'yo'

    # 1) Build one row PER TOKEN-PER ATOMIC FEATURE
    df_atoms = process_dir(DATA_DIR, GLOSS_COL, GOLD_COL, LANGUAGE)

    # 2) Compute per-label metrics
    report_df = compute_per_label_report(df_atoms)
    print("\nPer‑atomic‑feature classification report:\n")
    print(report_df.round(3))

    # 3) Plot metrics
    plot_metrics(report_df, LANGUAGE)

    # 4) Overall multilabel metrics
    mlb = MultiLabelBinarizer()
    y_true = mlb.fit_transform(df_atoms['gold'])
    y_pred = mlb.transform(df_atoms['pred'])

    overall_acc = accuracy_score(y_true, y_pred)
    overall_hl  = hamming_loss(y_true, y_pred)
    print(f"\nOverall subset accuracy: {overall_acc:.3f}")
    print(f"Overall hamming_loss:    {overall_hl:.3f}")
