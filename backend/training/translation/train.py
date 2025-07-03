import os
import torch
from torch.utils.data import Dataset, DataLoader
import pandas as pd
from transformers import (
    M2M100ForConditionalGeneration,
    M2M100Tokenizer,
    get_linear_schedule_with_warmup
)
from training.preprocessing import build_translationset
from torch.optim import AdamW



class TranslationDataset(Dataset):
    def __init__(self, texts, summaries, tokenizer, src_lang, tgt_lang, max_length=128):
        self.tokenizer = tokenizer
        self.texts = texts
        self.summaries = summaries
        self.max_length = max_length
        self.src_lang = src_lang
        self.tgt_lang = tgt_lang

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        src = self.texts[idx]
        tgt = self.summaries[idx]
        # tokenize
        inputs = self.tokenizer(
            src,
            return_tensors="pt",
            padding="max_length",
            truncation=True,
            max_length=self.max_length
        )
        with self.tokenizer.as_target_tokenizer():
            targets = self.tokenizer(
                tgt,
                return_tensors="pt",
                padding="max_length",
                truncation=True,
                max_length=self.max_length
            )
        input_ids = inputs.input_ids.squeeze()
        attention_mask = inputs.attention_mask.squeeze()
        labels = targets.input_ids.squeeze()
        # replace padding token id's of the labels by -100 so it's ignored by the loss
        labels[labels == self.tokenizer.pad_token_id] = -100
        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "labels": labels,
        }


def train_m2m100(
    lang: str,
    study: str,
    input_dir: str,
    epochs: int = 5,
    batch_size: int = 8,
    lr: float = 5e-5,
    max_length: int = 128,
    device: torch.device = None,
):
    # Prepare device
    device = device or (torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu"))
    print(f"Using device: {device}")

    # Build or refresh translation dataset
    build_translationset(lang, study, input_dir)
    data_path = f"training/data/{lang}_{study}_train_translation.xlsx"
    df = pd.read_excel(data_path)
    src_texts = df["text"].tolist()
    tgt_texts = df["translation"].tolist()

    # Load model & tokenizer
    model_name = "facebook/m2m100_418M"
    tokenizer = M2M100Tokenizer.from_pretrained(model_name)
    tokenizer.src_lang = lang
    tokenizer.tgt_lang = "en"
    model = M2M100ForConditionalGeneration.from_pretrained(model_name).to(device)

    # Prepare dataset and dataloader
    dataset = TranslationDataset(src_texts, tgt_texts, tokenizer, lang, "en", max_length)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    # Optimizer & scheduler
    optimizer = AdamW(model.parameters(), lr=lr)
    total_steps = len(dataloader) * epochs
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=int(0.1 * total_steps),
        num_training_steps=total_steps,
    )

    model.train()
    for epoch in range(1, epochs + 1):
        total_loss = 0.0
        for batch in dataloader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)

            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                labels=labels,
            )
            loss = outputs.loss
            total_loss += loss.item()

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            scheduler.step()

        avg_loss = total_loss / len(dataloader)
        print(f"Epoch {epoch}/{epochs} — loss: {avg_loss:.4f}")

    # Save fine-tuned model and tokenizer
    output_dir = f"models/translation/{lang}_{study}_custom_translation"	
    os.makedirs(output_dir, exist_ok=True)
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    print(f"Model and tokenizer saved to {output_dir}")

if __name__ == "__main__":
    lang= "yo"
    study = "H"
    input_dir = "C:/Users/camelo.cruz/Leibniz-ZAS/Leibniz Dream Data - Studies/H_Dependencies/H06a-Relative-Clause-Production-study/H06a_raw_files_yor/H06a_raw_files_yor_adults/data_1732047553925"
    train_m2m100(lang, study, input_dir)