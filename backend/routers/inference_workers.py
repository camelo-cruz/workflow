import os
import tempfile
import traceback
import shutil
from zipfile import ZipFile
from pathlib import Path

from inference.data_processors.factory import ProcessorFactory
from utils.onedrive import (
    download_sharepoint_folder,
    upload_file_replace_in_onedrive,
    list_session_children,
)

class BaseWorker:
    def __init__(self, base_dir, action, language, instruction,
                 translationModel, glossingModel, job_id=0, q=None, cancel=None):
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
        # By default, just process the single base_dir
        yield self.base_dir

    def after_process(self, folder_path):
        # Hook: override in subclasses for per‐folder teardown (e.g. zipping or uploading)
        pass

    def run(self):
        try:
            self.initial_message()
            for folder in self.folder_to_process():
                if self.cancel.is_set():
                    self.put("[CANCELLED]")
                    break

                session_name = os.path.basename(folder.rstrip(os.sep))
                self.put(f"Processing session: {session_name}")

                processor = ProcessorFactory.get_processor(
                    self.language,
                    self.action,
                    self.instruction,
                    self.translationModel,
                    self.glossingModel,
                )
                processor.process(folder)
                self.after_process(folder)

        except Exception as e:
            self.put(f"[ERROR] {e}")
            self.put(traceback.format_exc())
        finally:
            self.put("[DONE ALL]")

class ZipWorker(BaseWorker):
    """
    Processes a single local folder (or multiple if your base_dir contains
    sub-folders named “Session_*”), then zips up only the output files you care
    about and reports the zip path.
    """
    def initial_message(self):
        self.put("Preparing to process and zip outputs…")

    def after_process(self, folder_path):
        # Name the zip after the job
        zip_path = Path(tempfile.gettempdir()) / f"{self.job_id}_output.zip"
        with ZipFile(zip_path, "w") as zf:
            # Walk the processed folder and only include certain filenames
            for root, _, files in os.walk(folder_path):
                for fname in files:
                    if fname in (
                        "trials_and_sessions_annotated.xlsx",
                        "transcription.log",
                        "translation.log",
                    ):
                        full = os.path.join(root, fname)
                        # make the archive paths relative to the base_dir
                        rel = os.path.relpath(full, self.base_dir)
                        zf.write(full, arcname=rel)
        self.put(f"[ZIP PATH] {zip_path}")


class OneDriveWorker(BaseWorker):
    """
    Downloads every session folder from a OneDrive share, processes them,
    then uploads the outputs back to OneDrive and cleans up.
    """
    def __init__(self, job_id, base_dir, action, language, instruction,
                 translationModel, glossingModel, q, cancel,
                 share_link, token):
        super().__init__(job_id, base_dir, action, language, instruction,
                         translationModel, glossingModel, q, cancel)
        self.share_link = share_link
        self.token = token
        self.sessions_meta = []

    def initial_message(self):
        self.put("Checking for sessions on OneDrive…")
        metas = list_session_children(self.share_link, self.token)
        if not metas:
            metas = [{"webUrl": self.share_link, "name": None}]
        self.sessions_meta = metas
        self.put(f"Found {len(self.sessions_meta)} session(s).")

    def folder_to_process(self):
        for meta in self.sessions_meta:
            if self.cancel.is_set():
                break

            link = meta["webUrl"]
            name = meta.get("name") or "session"
            self.put(f"Downloading session '{name}'…")
            tmp_dir = tempfile.mkdtemp()
            try:
                inp, drive_id, _, sess_map = download_sharepoint_folder(
                    share_link=link,
                    temp_dir=tmp_dir,
                    access_token=self.token,
                )
            except Exception as e:
                self.put(f"Failed to download '{name}': {e}. Skipping.")
                shutil.rmtree(tmp_dir, ignore_errors=True)
                continue

            # session folder on disk
            session_path = os.path.join(inp, name)
            if not os.path.isdir(session_path):
                session_path = inp

            # stash some state for after_process
            self._current = {
                "tmp_dir": tmp_dir,
                "drive_id": drive_id,
                "sess_map": sess_map,
                "session_name": name,
            }
            yield session_path

    def after_process(self, folder_path):
        info = self._current
        name = info["session_name"]
        drive_id = info["drive_id"]
        sess_map = info["sess_map"]
        tmp_dir = info["tmp_dir"]

        # upload any relevant outputs
        uploads = [
            "trials_and_sessions_annotated.xlsx",
            f"{ProcessorFactory.get_processor.__qualname__}.log"
        ]
        for fname in uploads:
            if self.cancel.is_set():
                self.put("[CANCELLED UPLOAD]")
                break
            local_fp = os.path.join(folder_path, fname)
            if not os.path.exists(local_fp):
                self.put(f"Skipping missing file: {fname}")
                continue

            parent_id = sess_map.get(name, "")
            self.put(f"Uploading '{fname}' for session '{name}'…")
            upload_file_replace_in_onedrive(
                local_file_path=local_fp,
                target_drive_id=drive_id,
                parent_folder_id=parent_id,
                file_name_in_folder=fname,
                access_token=self.token,
            )

        shutil.rmtree(tmp_dir, ignore_errors=True)
        self.put(f"[DONE UPLOADED] {name}")

class TrainSpacyWorker(BaseWorker):
    pass
