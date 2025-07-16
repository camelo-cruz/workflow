from training.training.SpacyTrainer import SpacyTrainer
class TrainerFactory:
    @staticmethod
    def get_trainer(action, language: str, study: str):
        if action == "gloss":
            return SpacyTrainer(language, study)