import os
import traceback
import argparse

from inference.processors.factory import ProcessorFactory

class BaseWorker:
    def __init__(self, base_dir, action, language, instruction,
                 translationModel=None, glossingModel=None, job_id=0, q=None, cancel=None):
        self.job_id = job_id
        self.base_dir = base_dir
        self.action = action
        self.language = language
        self.instruction = instruction
        self.translationModel = translationModel
        self.glossingModel = glossingModel
        self.q = q
        self.cancel = cancel

    def put(self, msg):
        if self.q:
            self.q.put(msg)
        else:
            print(msg)

    def initial_message(self):
        # Hook: override in subclasses if you need to log or prepare before processing.
        self.put(f"Starting job {self.job_id} – action: {self.action}")

    def folder_to_process(self):
        # By default, just process the single base_dir. In some cases
        # you might want to override this to yield multiple folders.
        yield self.base_dir

    def after_process(self, folder_path):
        # Hook: override in subclasses for per‐folder teardown (e.g. zipping or uploading)
        pass

    def run(self):
        try:
            self.initial_message()
            for folder in self.folder_to_process():
                if self.cancel and self.cancel.is_set():
                    self.put("[CANCELLED]")
                    break

                session_name = os.path.basename(os.path.normpath(folder))
                self.put(f"Processing session: {session_name}")

                self.processor = ProcessorFactory.get_processor(
                    self.language,
                    self.action,
                    self.instruction,
                    self.translationModel,
                    self.glossingModel,
                )
                self.processor.process(folder)
                self.after_process(folder)

        except Exception as e:
            self.put(f"[ERROR] {e}")
            self.put(traceback.format_exc())
        finally:
            self.put("[DONE ALL]")

def main():
    parser = argparse.ArgumentParser(
        description="Run BaseWorker from the command line"
    )
    parser.add_argument("--base-dir", required=True,
                        help="Path to the folder you want to process")
    parser.add_argument("--action",    required=True,
                        choices=['transcribe', 'translate', 'transliterate', 'gloss'],)
    parser.add_argument("--language",  required=True,
                        help="Language name (e.g. 'spanish', 'english')")
    parser.add_argument("--instruction", default=None,
                        choices=['automatic', 'corrected', 'sentences'],
                        help="Processor instruction for translation or glossing")
    parser.add_argument("--translation-model", default=None,
                        help="Optional name of the translation model")
    parser.add_argument("--glossing-model",  default=None,
                        help="Optional name of the glossing model")
    parser.add_argument("--job-id", type=int, default=0,
                        help="Numeric job identifier (default: 0)")

    args = parser.parse_args()

    worker = BaseWorker(
        base_dir = args.base_dir,
        action = args.action,
        language = args.language,
        instruction = args.instruction,
        translationModel = args.translation_model,
        glossingModel = args.glossing_model,
        job_id = args.job_id,
    )
    worker.run()


if __name__ == "__main__":
    main()

# use example:
# inside the backend directory:
# python inference/worker.py --base-dir /path/to/session --action translate --language german --instruction automatic
