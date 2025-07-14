import logging
import tempfile
import shutil
import requests
from pathlib import Path
from typing import List, Dict, Optional

from training.glossing.train_spacy import train_spacy
from training.translation.train import train_m2m100
from training.preprocessing.spacy import GlossingPreprocessor
from routers.helpers.onedrive import (
    download_sharepoint_folder,
    upload_file_replace_in_onedrive,
    encode_share_link,
    list_session_children
)

# Configure module-level logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OneDriveWorker():
    def __init__(self, base_dir, action, language, instruction,
                 translationModel, glossingModel, study, token, job):
        super().__init__(base_dir, action, language, instruction,
                         translationModel, glossingModel, job)
        self.share_link = base_dir
        self.token = token
        self.study = study
        self.sessions_meta = []
        # Fetch metadata for the shared item
        metadata_url = f"https://graph.microsoft.com/v1.0/shares/{encode_share_link(self.share_link)}/driveItem"
        resp = requests.get(metadata_url, headers={"Authorization": f"Bearer {self.token}"})
        resp.raise_for_status()
        self.item = resp.json()

        self.root_drive_id = self.item["parentReference"]["driveId"]
        self.root_parent_folder_id = self.item["id"]

    def run(self):
        self.put(f"[INFO] Job {self.job_id}: downloading sessions")

        # Download and collect session folders
        try:
            sessions = self._gather_sessions()
        except Exception as e:
            self.put(f"[ERROR] Failed to download sessions: {e}")
            logger.exception("Download sessions error")
            return

        if not sessions:
            self.put(f"[ERROR] No sessions available for training")
            return

        # Create temporary root for processing
        with tempfile.TemporaryDirectory(prefix=f"{self.job_id}_") as tmpdir:
            temp_root = Path(tmpdir)
            self.temp_root = temp_root  # store for after_process

            self.put(f"[INFO] Starting training phase")
            try:
                if self.action == "gloss":
                    preprocessor = GlossingPreprocessor(
                        input_dir=str(temp_root),
                        lang=self.language,
                        study=self.study
                    )
                    preprocessor.preprocess()
                else:
                    self.put(f"[WARNING] Unsupported action '{self.action}'")
                    return
            except Exception as e:
                self.put(f"[ERROR] Training failed: {e}")
                logger.exception("Training error")
                return

            self.put("[DONE ALL]")

        self.put(f"[INFO] Cleaned up temporary files for job {self.job_id}")

        # After process/upload logs
        self.after_process()

    def _gather_sessions(self) -> List[Dict[str, str]]:
        """List and download session folders to a temporary root directory."""
        entries = list_session_children(self.share_link, self.token) or [
            {"webUrl": self.share_link, "name": None}
        ]
        sessions: List[Dict[str, str]] = []

        for entry in entries:
            name = entry.get("name") or "root"
            self.put(f"[INFO] Downloading session '{name}'...")
            local_dir = Path(tempfile.mkdtemp(prefix=f"{self.job_id}_")) / name
            local_dir.mkdir(parents=True, exist_ok=True)

            try:
                inp_dir, drive_id, parent_folder_id, _ = download_sharepoint_folder(
                    share_link=entry["webUrl"],
                    temp_dir=str(local_dir),
                    access_token=self.token,
                    file_suffix=["annotated.xlsx"]
                )
            except Exception as e:
                self.put(f"[ERROR] Download failed for '{name}': {e}")
                logger.exception("Download error for session %s", name)
                continue

            inp_path = Path(inp_dir)
            session_path = inp_path / name if (inp_path / name).is_dir() else inp_path

            sessions.append({
                "name": name,
                "drive_id": drive_id,
                "parent_folder_id": parent_folder_id,
                "local_path": str(session_path)
            })

        return sessions

    def after_process(self):
        """Upload the training log back to OneDrive."""
        log_file = Path(self.temp_root) / "glossing_traindata.log"
        if not log_file.exists():
            self.put(f"[WARNING] Log file {log_file} not found, skipping upload")
            return

        try:
            # Upload to the original folder
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
