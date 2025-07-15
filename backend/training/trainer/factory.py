from training.trainer.glossing.train_spacy import SpacyTrainer
class TrainerFactory:
    @staticmethod
    def get_trainer(action, language: str, study: str):
        if action == "gloss":
            return SpacyTrainer(language, study)