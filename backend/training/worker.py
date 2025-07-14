import traceback
import argparse
from training.preprocessing.UD import UDPreprocessor

class TrainingWorker:
    def __init__(self, base_dir, language, action, study, job=None):
        self.base_dir = base_dir
        self.language = language
        self.action = action
        self.study = study
        self.job = job

        self.job_id = job.id if job else None
        self.q = job.queue if job else None
        self.cancel = job.cancel_event if job else None
    
    def put(self, msg):
        if self.q:
            self.q.put(msg)
        else:
            print(msg)
    
    def run(self):
        try:
            self.put(f"Starting training job {self.job_id} – action: {self.action}")

            preprocessor = UDPreprocessor(
                lang=self.language,
                study=self.study,
                file_pattern="*annotated.xlsx"
            )
            preprocessor.preprocess(self.base_dir)

            self.put(f"Training completed for job {self.job_id}")

        except Exception as e:
            self.put(f"[ERROR] {str(e)}")
            traceback.print_exc()
        finally:
            if self.cancel and self.cancel.is_set():
                self.put("[CANCELLED]")

def main():
    parser = argparse.ArgumentParser(
        description="Run the UD training preprocessing for a given study."
    )
    parser.add_argument(
        "base_dir",
        help="Path to the directory containing annotated files"
    )
    parser.add_argument(
        "language",
        help="Language code for preprocessing (e.g., 'en', 'de')"
    )
    parser.add_argument(
        "action",
        help="Action to perform (e.g., 'preprocess')"
    )
    parser.add_argument(
        "study",
        help="Study identifier or name"
    )

    args = parser.parse_args()

    worker = TrainingWorker(
        base_dir=args.base_dir,
        language=args.language,
        action=args.action,
        study=args.study
    )
    worker.run()

if __name__ == "__main__":
   worker = TrainingWorker(
        base_dir='/Users/alejandra/Library/CloudStorage/OneDrive-FreigegebeneBibliotheken–Leibniz-ZAS/Leibniz Dream Data - Studies/tests_alejandra/yoruba/data_1732047553925 Kopie',
        language='yoruba',
        action='gloss',
        study='H'
    )
   worker.run()