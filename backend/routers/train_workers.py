import os
import shutil
import tempfile
import traceback
import requests
import base64

from pathlib import Path
from training.glossing.train_spacy import train_spacy
from training.translation.train import train_m2m100
from training.preprocessing.spacy import GlossingPreprocessor
from utils.onedrive import (download_sharepoint_folder, 
                            upload_file_replace_in_onedrive, 
                            encode_share_link,
                            list_session_children)

def _online_train_worker(
    job_id: str,
    share_link: str,
    token: str,
    action: str,
    language: str,
    study: str,
    q,
    cancel
):
    def put(msg: str):
        q.put(msg)

    share_id = encode_share_link(share_link)
    root_url = f"https://graph.microsoft.com/v1.0/shares/{share_id}/driveItem"
    resp = requests.get(root_url, headers={"Authorization": f"Bearer {token}"})
    resp.raise_for_status()
    root_item = resp.json()
    root_drive_id        = root_item["parentReference"]["driveId"]
    root_parent_folder_id = root_item["id"]

    root_tmp = tempfile.mkdtemp(prefix=f"{job_id}_")
    sessions = []

    try:
        put(f"[INFO] Job {job_id}: listing sessions…")
        meta_entries = list_session_children(share_link, token)
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
        
        
        put(f"[INFO] Training model. This may take a while…")
        try:
            if action == "gloss":
                preprocessor = GlossingPreprocessor(input_dir=root_tmp, lang=language, study=study)
                preprocessor.preprocess()
                # --- UPLOAD ONE LOG AT ROOT LEVEL ---
                output = "glossing_traindata.log" if action == "gloss" else "translation_traindata.log"
                try:
                    upload_file_replace_in_onedrive(
                        local_file_path=str(Path(root_tmp) / output),
                        target_drive_id=root_drive_id,
                        parent_folder_id=root_parent_folder_id,
                        file_name_in_folder=output,
                        access_token=token,
                    )
                    put(f"[INFO] Uploaded '{output}' to root folder")
                except Exception as e:
                    put(f"[ERROR] Upload failed for '{output}': {e}")
                    put(traceback.format_exc())

                train_spacy(root_tmp, language, study)
            elif action == "translate":
                train_m2m100(root_tmp, language, study)
            else:
                put(f"[WARNING] Unknown action '{action}', skipping training")
        except Exception as e:
            put(f"[ERROR] Training error: {e}")
            put(traceback.format_exc())
            return
        put("[DONE ALL]")
    finally:
        # always clean up the entire root_tmp
        shutil.rmtree(root_tmp, ignore_errors=True)
        put(f"[INFO] Cleaned up all temp dirs for job {job_id}")
        put(f"[DONE ALL]")

def _offline_train_worker():
    pass