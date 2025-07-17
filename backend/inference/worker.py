import os
import traceback
import argparse
from abc import ABC, abstractmethod

from inference.processors.factory import ProcessorFactory


class AbstractInferenceWorker(ABC):
    """
    Abstract base class for inference workers that process data folders using
    dynamic processors from ProcessorFactory. Subclasses should implement
    lifecycle hooks: initial_message, folder_to_process, and after_process.
    """

    def __init__(self, base_dir: str, action: str, language: str, instruction: str,
                 translationModel: str = None, glossingModel: str = None, job=None):
        """
        Initialize the inference worker with configuration parameters.

        Args:
            base_dir (str): Path to the root directory for processing.
            action (str): Action type (e.g., 'transcribe', 'translate', 'gloss').
            language (str): Language code or name.
            instruction (str): Instruction mode (e.g., 'automatic', 'corrected').
            translationModel (str, optional): Name of translation model to use.
            glossingModel (str, optional): Name of glossing model to use.
            job (optional): Job object providing id, queue, and cancel_event.
        """
        self.base_dir = base_dir
        self.current_folder = self.base_dir
        self.action = action
        self.language = language
        self.instruction = instruction
        self.translationModel = translationModel
        self.glossingModel = glossingModel
        self.job = job

        # Setup job identification and messaging queue
        self.job_id = job.id if job else 'local_job'
        self.q = getattr(job, 'queue', None)
        self.cancel = getattr(job, 'cancel_event', None)

    @abstractmethod
    def _initial_message(self) -> None:
        """
        Hook for sending an initial start-up message.
        """
        raise NotImplementedError("Subclasses must implement initial_message()")

    @abstractmethod
    def _folder_to_process(self):
        """
        Hook for yielding or listing directories to process.

        Returns:
            Iterable[str]: A sequence of folder paths.
        """
        yield self.current_folder

    @abstractmethod
    def _after_process(self) -> None:
        """
        Actions to perform immediately after preprocessing step completes.
        use self.current_folder to access the folder being processed.
        """
        raise NotImplementedError("Subclasses must implement after_process()")
    
    def put(self, msg: str) -> None:
        """
        Send a status message to the job queue or print to console.

        Args:
            msg (str): Message content.
        """
        if self.q:
            self.q.put(msg)
        else:
            print(msg)

    def run(self) -> None:
        """
        Execute the inference workflow: send initial message, iterate over
        folders, instantiate the appropriate processor, and process each folder.
        Handles cancellation and exceptions.
        """
        try:
            # Notify start
            self.initial_message()

            # Iterate through target directories
            for folder in self.folder_to_process():
                self.current_folder = folder
                # Check for cancellation
                if self.cancel and self.cancel.is_set():
                    self.put("[CANCELLED]")
                    break

                # Report current session folder
                session_name = os.path.basename(os.path.normpath(self.current_folder))
                self.put(f"Processing session: {session_name}")

                # Create a processor based on configuration
                self.processor = ProcessorFactory.get_processor(
                    self.language,
                    self.action,
                    self.instruction,
                    self.translationModel,
                    self.glossingModel,
                )

                # Run the processing logic
                self.processor.process(self.current_folder)

                # Post-processing hook
                self.after_process()

        except Exception as e:
            # Report errors and stack trace
            self.put(f"[ERROR] {e}")
            self.put(traceback.format_exc())
        finally:
            # Always signal completion
            self.put("[DONE ALL]")


class LocalWorker(AbstractInferenceWorker):
    """
    Local implementation of AbstractInferenceWorker for CLI or API usage.
    Defines simple folder iteration and messaging behavior.
    """

    def _initial_message(self) -> None:
        """
        Print or queue the initial job start message.
        """
        self.put(f"Starting job {self.job_id} – action: {self.action}")

    def _folder_to_process(self):
        """
        Yield the single base directory for processing.

        Yields:
            str: The base directory path.
        """
        yield self.base_dir

    def _after_process(self) -> None:
        """
        Print or queue a message after processing a folder.
        """
        self.put(f"Processed folder {self.current_folder} for job {self.job_id}")


def main() -> None:
    """
    Command-line interface entry point for running inference workers.

    Parses arguments, initializes LocalWorker, and invokes run().
    """
    parser = argparse.ArgumentParser(
        description="Run inference worker from the command line."
    )
    parser.add_argument(
        "--base-dir", required=True,
        help="Path to the folder to process"
    )
    parser.add_argument(
        "--action", required=True,
        choices=['transcribe', 'translate', 'transliterate', 'gloss'],
        help="Action to perform"
    )
    parser.add_argument(
        "--language", required=True,
        help="Language code (e.g., 'spanish', 'english')"
    )
    parser.add_argument(
        "--instruction", default=None,
        choices=['automatic', 'corrected', 'sentences'],
        help="Instruction for translation or glossing"
    )
    parser.add_argument(
        "--translation-model", default=None,
        help="Name of translation model (optional)"
    )
    parser.add_argument(
        "--glossing-model", default=None,
        help="Name of glossing model (optional)"
    )
    parser.add_argument(
        "--job-id", type=int, default=0,
        help="Numeric job identifier"
    )

    args = parser.parse_args()

    # Instantiate and run the local worker
    worker = LocalWorker(
        base_dir=args.base_dir,
        action=args.action,
        language=args.language,
        instruction=args.instruction,
        translationModel=args.translation_model,
        glossingModel=args.glossing_model,
        job=None  # CLI usage, no job object
    )
    worker.run()


if __name__ == "__main__":
    main()
