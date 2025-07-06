import os
from pathlib import Path

import pandas as pd
from wasabi import msg

from training.preprocessing.abstract import BasePreprocessor


class TranslationPreprocessor(BasePreprocessor):
    """
    Preprocess translation data to produce sentence- and token-level Excel.
    """

    def preprocess(self) -> None:
        log_path = self.input_dir / 'translation_traindata.log'
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = self._setup_file_handler(log_path)

        records = []
        for root, _, files in os.walk(self.input_dir):
            for fname in files:
                if not fname.endswith('annotated.xlsx'):
                    continue
                df = pd.read_excel(Path(root) / fname).dropna(
                    subset=[self.TEXT_COLUMN, self.GLOSS_COLUMN, self.TRANSLATION_COLUMN]
                )
                df[self.TEXT_COLUMN] = df[self.TEXT_COLUMN].map(self._clean_text)
                df[self.GLOSS_COLUMN] = df[self.GLOSS_COLUMN].map(self._clean_text)
                df[self.TRANSLATION_COLUMN] = df[self.TRANSLATION_COLUMN].map(self._clean_text).str.lower()

                for _, row in df.iterrows():
                    sent, gloss_line, tr = row[self.TEXT_COLUMN], row[self.GLOSS_COLUMN], row[self.TRANSLATION_COLUMN]
                    t_tokens, g_tokens = sent.split(), gloss_line.split()
                    if len(t_tokens) != len(g_tokens):
                        msg.warn(f"Token mismatch in {fname}")
                        continue
                    records.append({"unit_type": "sentence", "text": sent, "translation": tr})
                    for tok, gloss_tok in zip(t_tokens, g_tokens):
                        head = gloss_tok.split('.')[0]
                        if head.islower():
                            records.append({"unit_type": "token", "text": tok, "translation": head})

        if records:
            out_path = Path('training/data') / f"{self.lang}_{self.study}_train_translation.xlsx"
            pd.DataFrame(records).to_excel(out_path, index=False)
            msg.good(f"Wrote {len(records)} translation rows")
        else:
            msg.warn("No translation records generated.")

        handler.close()
        self.logger.removeHandler(handler)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="Run data preprocessing steps.")
    parser.add_argument('--input_dir', required=True)
    parser.add_argument('--lang', required=True)
    parser.add_argument('--study', required=True)
    parser.add_argument('--config', default=str(Path(__file__).parent / 'glossing/configs/base_config.cfg'))
    parser.add_argument('--model', default=None)
    args = parser.parse_args()

    # Execute both steps
    glossor = GlossingPreprocessor(
        input_dir=args.input_dir,
        lang=args.lang,
        study=args.study,
        base_config_path=args.config,
        pretrained_model=args.model
    )
    glossor.preprocess()

    translator = TranslationPreprocessor(
        input_dir=args.input_dir,
        lang=args.lang,
        study=args.study,
        base_config_path=args.config,
        pretrained_model=args.model
    )
    translator.preprocess()
