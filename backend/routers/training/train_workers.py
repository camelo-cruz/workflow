import logging
import tempfile
from pathlib import Path
from typing import List, Dict

import requests
from training.worker import AbstractTrainingWorker
from routers.helpers.onedrive import (
    download_sharepoint_folder,
    upload_file_replace_in_onedrive,
    encode_share_link,
    list_session_children
)

# Configure module-level logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OneDriveWorker(AbstractTrainingWorker):
    def __init__(self, base_dir, language, action, study, token, job):
        super().__init__(base_dir, language, action, study, job)
        self.share_link = base_dir
        self.token = token
        self.sessions_meta = []

        self._tempdir_obj = tempfile.TemporaryDirectory(prefix=f"{self.job_id}_")
        self.temp_root = Path(self._tempdir_obj.name)

        # Optional: eager init to reduce surprises later
        # self._ensure_metadata()

    def _ensure_metadata(self):
        """Ensure drive/folder metadata is loaded on demand."""
        if hasattr(self, "root_drive_id") and hasattr(self, "root_parent_folder_id"):
            return
        try:
            metadata_url = (
                f"https://graph.microsoft.com/v1.0/shares/"
                f"{encode_share_link(self.share_link)}/driveItem"
            )
            resp = requests.get(metadata_url, headers={"Authorization": f"Bearer {self.token}"})
            resp.raise_for_status()
            self.item = resp.json()
            self.root_drive_id = self.item["parentReference"]["driveId"]
            self.root_parent_folder_id = self.item["id"]
        except Exception as e:
            self._put(f"Failed to fetch metadata for share link {self.share_link}: {e}")
            raise ValueError(f"Failed to fetch metadata for share link {self.share_link}: {e}")

    def _initial_message(self):
        self._put("Checking for sessions on OneDrive…")
        # Use the shared helper so all paths are consistent
        self._ensure_metadata()

    def _folder_to_preprocess(self) -> Path:
        """
        Download all session folders under the SharePoint link and return
        the root directory containing downloaded sessions.
        """
        self._put(f"[INFO] Temporary root directory: {self.temp_root}")
        entries = list_session_children(self.share_link, self.token)

        for entry in entries:
            name = entry.get("name", "root")
            self._put(f"[INFO] Downloading session '{name}'")

            session_dir = self.temp_root / name
            session_dir.mkdir(parents=True, exist_ok=True)

            try:
                download_sharepoint_folder(
                    share_link=entry["webUrl"],
                    temp_dir=str(session_dir),
                    access_token=self.token,
                    file_suffix=["annotated.xlsx"],
                )
            except Exception as e:
                self._put(f"[WARNING] Download failed for '{name}': {e}")
                logger.exception("Download error for session %s", name)
                continue

        # If your framework expects a generator, keep yield; otherwise return.
        yield self.temp_root

    def _after_preprocess(self):
        """ Upload the training log back to OneDrive, then delete the temp dir. """
        # Make sure drive/parent ids are present even if _initial_message wasn't called
        try:
            self._ensure_metadata()
        except Exception:
            # _put already messaged the failure in _ensure_metadata
            # proceed to cleanup to avoid leaving temp dirs behind
            self._tempdir_obj.cleanup()
            self._put(f"[INFO] Deleted temporary directory {self.temp_root}")
            return

        log_file = self.temp_root / f"{self.preprocessor.__class__.__name__}.log"
        if not log_file.exists():
            self._put(f"[WARNING] Log file {log_file} not found, skipping upload")
        else:
            try:
                upload_file_replace_in_onedrive(
                    local_file_path=str(log_file),
                    target_drive_id=self.root_drive_id,
                    parent_folder_id=self.root_parent_folder_id,
                    file_name_in_folder=log_file.name,
                    access_token=self.token
                )
                self._put(f"[INFO] Uploaded '{log_file.name}'")
            except Exception as e:
                self._put(f"[WARNING] Upload failed for '{log_file.name}': {e}")
                logger.exception("Upload error for %s", log_file)

        self._tempdir_obj.cleanup()
        self._put(f"[INFO] Deleted temporary directory {self.temp_root}")
    
    def _after_train(self):
        return super()._after_train()
