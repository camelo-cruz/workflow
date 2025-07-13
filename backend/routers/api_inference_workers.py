import os
import tempfile
import traceback
import shutil
from zipfile import ZipFile
from pathlib import Path

from inference.processors.factory import ProcessorFactory
from inference.worker import BaseWorker
from utils.onedrive import (
    download_sharepoint_folder,
    upload_file_replace_in_onedrive,
    list_session_children,
)

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
        self.sessions_meta = list_session_children(self.share_link, self.token)

        if not self.sessions_meta:
            # if there are no nested Session_ folders, assume share_link points directly to a single Session
            self.sessions_meta = [{"webUrl": self.share_link}]
        self.put(f"Found {len(self.sessions_meta)} session(s).")

    def folder_to_process(self):
        for meta in self.sessions_meta:
            if self.cancel.is_set():
                break

            link = meta.get("webUrl")
            self.put(f"Downloading from OneDrive")
            tmp_dir = tempfile.mkdtemp()
            try:
                inp, drive_id, _, sess_map = download_sharepoint_folder(
                    share_link=link,
                    temp_dir=tmp_dir,
                    access_token=self.token,
                )
            except Exception as e:
                self.put(f"Failed to download session': {e}. Skipping.")
                shutil.rmtree(tmp_dir, ignore_errors=True)
                continue

            # session folder on disk

            name = meta.get("name") or next(iter(sess_map.keys()), Path(inp).name)
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
            f"{self.processor.__class__.__name__}.log"
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
            self.put(f"Uploading '{fname}' for session '{name}'")
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
