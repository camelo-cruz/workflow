import traceback
import argparse
from training.preprocessing.UD import UDPreprocessor
from abc import ABC, abstractmethod


class AbstractTrainingWorker(ABC):
    """
    Abstract base class for training workers that handle preprocessing and training tasks.

    Subclasses must implement methods to produce initial messages, determine the folder to process,  
    and define actions after preprocessing and after training.
    """
    def __init__(self, base_dir, language, action, study, job=None):
        """
        Initialize the worker with job configuration.

        Args:
            base_dir (str): Root directory containing study data.
            language (str): Language code (e.g., 'en', 'de', 'yoruba').
            action (str): Task action (e.g., 'preprocess', 'train', 'gloss').
            study (str): Study identifier or name.
            job (optional): Optional job object when running in a queued environment.
        """
        self.base_dir = base_dir
        self.language = language
        self.action = action
        self.study = study
        self.job = job

        # Determine job-related identifiers and messaging queue
        self.job_id = job.id if job else 'local_job'
        self.q = job.queue if job else None
        self.cancel = job.cancel_event if job else None
    
    def _put(self, msg):
        """
        Send a message to the job queue or print to stdout if no queue is provided.

        Args:
            msg (str): Message to send or print.
        """
        if self.q:
            self.q.put(msg)
        else:
            print(msg)

    @abstractmethod
    def _initial_message(self):
        """Return the initial start message for the worker."""
        pass

    @abstractmethod
    def _folder_to_process(self):
        """Determine and return the folder path to be processed."""
        pass

    @abstractmethod
    def _after_preprocess(self):
        """Actions to perform immediately after preprocessing step completes.
        use self.current_folder to access the folder being processed."""
        pass

    @abstractmethod
    def _after_train(self):
        """Actions to perform immediately after training step completes."""
        pass

    def _preprocess(self):
        """
        Execute the preprocessing workflow using UDPreprocessor.

        This method sends status messages before and after processing.
        """
        self._put(f"Starting preprocessing for job {self.job_id} – action: {self.action}")
        self.preprocessor = UDPreprocessor(
            lang=self.language,
            study=self.study,
            file_pattern="*annotated.xlsx"
        )
        # Run preprocessing on target folder
        self.preprocessor.preprocess(self._folder_to_process())
        self._after_preprocess()
        self._put(f"Preprocessing completed for job {self.job_id}")

    def _train(self):
        """
        Execute the training workflow.

        Subclasses should override this method to implement specific training logic.
        """
        pass

    def run(self):
        """
        Entry point to run preprocessing and training in sequence.

        Captures exceptions and ensures a final completion message.
        """
        self._put(f"Starting job {self.job_id} – action: {self.action}")
        try:
            self._preprocess()
            self._train()
        except Exception as e:
            self._put(f"[ERROR] {str(e)}")
            traceback.print_exc()
        finally:
            self._put("[DONE ALL]")


class TrainingWorker(AbstractTrainingWorker):
    """
    Concrete training worker for local CLI or API execution.

    Implements abstract methods for local usage context.
    """
    def __init__(self, base_dir, language, action, study, job=None):
        super().__init__(base_dir, language, action, study, job)

    def _initial_message(self):
        return f"Initializing local training worker for {self.language}"

    def _folder_to_process(self):
        """Return the base directory for processing."""
        return self.base_dir

    def _after_preprocess(self):
        self._put(f"Local preprocessing completed for job {self.job_id} – action: {self.action}")

    def _after_train(self):
        self._put(f"Local training completed for job {self.job_id} – action: {self.action}")

    def _train(self):
        """
        Example training logic placeholder.

        Replace this method's content with actual training steps (e.g., model.fit()).
        """
        # Placeholder for training implementation
        self._put(f"Training logic for {self.language} with action {self.action} would run here.")
        self._after_train()


def main():
    """
    CLI entry point for running the training preprocessing.

    Parses command-line arguments and executes the TrainingWorker.
    """
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
        help="Action to perform (e.g., 'preprocess', 'train', 'gloss')"
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
    main()