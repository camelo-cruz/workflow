import logging
import tempfile
from pathlib import Path
from typing import List, Dict

import requests
from training.worker import TrainingWorker
from routers.helpers.onedrive import (
    download_sharepoint_folder,
    upload_file_replace_in_onedrive,
    encode_share_link,
    list_session_children
)

# Configure module-level logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OneDriveWorker(TrainingWorker):
    def __init__(self, base_dir, language, action, study, token, job):
        super().__init__(base_dir, language, action, study, job)
        self.share_link = base_dir
        self.token = token
        self.sessions_meta = []

        self._tempdir_obj = tempfile.TemporaryDirectory(prefix=f"{self.job}_")
        self.temp_root = Path(self._tempdir_obj.name)

        # Fetch metadata for the shared item
        metadata_url = (
            f"https://graph.microsoft.com/v1.0/shares/"
            f"{encode_share_link(self.share_link)}/driveItem"
        )
        resp = requests.get(metadata_url, headers={"Authorization": f"Bearer {self.token}"})
        resp.raise_for_status()
        self.item = resp.json()
        self.root_drive_id = self.item["parentReference"]["driveId"]
        self.root_parent_folder_id = self.item["id"]

    def folder_to_process(self) -> List[Dict[str, str]]:
        self.put(f"[INFO] Temporary root directory: {self.temp_root}")
        entries = list_session_children(self.share_link, self.token)

        for entry in entries:
            name = entry.get("name", "root")
            self.put(f"[INFO] Downloading session '{name}'")

            session_dir = self.temp_root / name
            session_dir.mkdir(parents=True, exist_ok=True)

            try:
                inp_dir, drive_id, parent_id, children = download_sharepoint_folder(
                    share_link=entry["webUrl"],
                    temp_dir=str(session_dir),
                    access_token=self.token,
                    file_suffix=["annotated.xlsx"],
                )
            except Exception as e:
                self.put(f"[ERROR] Download failed for '{name}': {e}")
                logger.exception("Download error for session %s", name)
                continue

        # Return the path your TrainingWorker expects:
        return str(self.temp_root)

    def after_preprocess(self):
        """ Upload the training log back to OneDrive, then delete the temp dir. """
        log_file = self.temp_root / f"{self.preprocessor.__class__.__name__}.log"
        if not log_file.exists():
            self.put(f"[WARNING] Log file {log_file} not found, skipping upload")
        else:
            try:
                upload_file_replace_in_onedrive(
                    local_file_path=str(log_file),
                    target_drive_id=self.root_drive_id,
                    parent_folder_id=self.root_parent_folder_id,
                    file_name_in_folder=log_file.name,
                    access_token=self.token
                )
                self.put(f"[INFO] Uploaded '{log_file.name}'")
            except Exception as e:
                self.put(f"[ERROR] Upload failed for '{log_file.name}': {e}")
                logger.exception("Upload error for %s", log_file)

        self._tempdir_obj.cleanup()
        self.put(f"[INFO] Deleted temporary directory {self.temp_root}")
