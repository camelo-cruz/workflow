import os
import shutil
import tempfile
import traceback
import requests
import base64

from pathlib import Path
from utils.onedrive import download_sharepoint_folder, upload_file_replace_in_onedrive
from training.glossing.train import train_spacy
from training.translation.train import train_m2m100

def _list_session_children(share_link: str, token: str):
    """
    List all 'Session_*' folders under a OneDrive share link.
    """
    share_id = base64.urlsafe_b64encode(share_link.encode()).decode().rstrip("=")
    url = f"https://graph.microsoft.com/v1.0/shares/u!{share_id}/driveItem/children"
    resp = requests.get(url, headers={"Authorization": f"Bearer {token}"})
    resp.raise_for_status()
    entries = resp.json().get("value", [])
    return [
        entry for entry in entries
        if entry.get("folder") and entry["name"].startswith("Session_")
    ]

def _online_train_worker(
    job_id: str,
    share_link: str,
    token: str,
    action: str,
    language: str,
    instruction: str,
    q,       # multiprocessing.Queue
    cancel   # multiprocessing.Event
):
    def put(msg: str):
        q.put(msg)

    root_tmp = tempfile.mkdtemp(prefix=f"{job_id}_")
    sessions = []

    try:
        put(f"[INFO] Job {job_id}: listing sessions…")
        meta_entries = _list_session_children(share_link, token)
        if not meta_entries:
            # treat the share link itself as one “root” session
            meta_entries = [{"webUrl": share_link, "name": None}]

        put(f"[INFO] Found {len(meta_entries)} session(s)")
        
        # Download each session under root_tmp/<session_name>
        for entry in meta_entries:
            if cancel.is_set():
                put("[WARNING] Cancelled during download phase")
                return

            name = entry.get("name") or "root"
            put(f"[INFO] Downloading session '{name}'")
            
            local_dir = os.path.join(root_tmp, name)
            os.makedirs(local_dir, exist_ok=True)

            try:
                # returns (downloaded_path, drive_id, parent_folder_id, _)
                inp_dir, drive_id, parent_folder_id, _ = download_sharepoint_folder(
                    share_link=entry["webUrl"],
                    temp_dir=local_dir,
                    access_token=token,
                    file_suffix=["annotated.xlsx"],
                )
            except Exception as e:
                put(f"[ERROR] Failed to download '{name}': {e}")
                put(traceback.format_exc())
                # leave missing sessions out of uploads
                continue

            # Normalize: if download created a subfolder named name, dive in
            candidate = Path(inp_dir) / name
            session_path = str(candidate if candidate.is_dir() else inp_dir)

            sessions.append({
                "name": name,
                "drive_id": drive_id,
                "parent_folder_id": parent_folder_id,
                "local_path": session_path
            })

        if not sessions:
            put("[ERROR] No sessions available to train")
            return

        # --- TRAIN ON ALL SESSIONS AT ONCE ---
        put(f"[INFO] Training model. This may take a while…")
        try:
            if action == "gloss":
                train_spacy(root_tmp, language, "cpu").process_data()
            elif action == "translate":
                train_m2m100(root_tmp, language, instruction, "cpu").process_data()
            else:
                put(f"[WARNING] Unknown action '{action}', skipping training")
        except Exception as e:
            put(f"[ERROR] Training error: {e}")
            put(traceback.format_exc())
            return

        # --- UPLOAD OUTPUTS PER SESSION ---
        outputs = ["training_data.log"]  # expand as needed
        for sess in sessions:
            if cancel.is_set():
                put("[WARNING] Cancelled during upload phase")
                return

            name = sess["name"]
            local_base = Path(sess["local_path"])
            put(f"[INFO] Uploading outputs for '{name}'")

            for fname in outputs:
                fp = local_base / fname
                if not fp.exists():
                    put(f"[WARNING] Missing output '{fname}' in '{name}', skipping")
                    continue

                put(f"[INFO] Uploading '{fname}' to OneDrive")
                try:
                    upload_file_replace_in_onedrive(
                        local_file_path=str(fp),
                        target_drive_id=sess["drive_id"],
                        parent_folder_id=sess["parent_folder_id"],
                        file_name_in_folder=fname,
                        access_token=token,
                    )
                    put(f"[INFO] Uploaded '{fname}' for '{name}'")
                except Exception as e:
                    put(f"[ERROR] Upload failed for '{name}/{fname}': {e}")
                    put(traceback.format_exc())

        put("[DONE ALL]")
    finally:
        # always clean up the entire root_tmp
        shutil.rmtree(root_tmp, ignore_errors=True)
        put(f"[INFO] Cleaned up all temp dirs for job {job_id}")

def _offline_train_worker():
    pass