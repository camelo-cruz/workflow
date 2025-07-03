import os
import shutil
import tempfile
import traceback
from pathlib import Path
import os
import tempfile
import traceback
import shutil
import queue
import requests
import base64

from zipfile import ZipFile
from pathlib import Path

from utils.onedrive import download_sharepoint_folder, upload_file_replace_in_onedrive
from training.glossing.train import train_spacy
from training.translation.train import train_m2m100

def _list_session_children(share_link: str, token: str):
    """
    Helper for the online worker: list all Session_* folders under a OneDrive share link.
    """
    share_id = base64.urlsafe_b64encode(share_link.encode()).decode().rstrip("=")
    url = f"https://graph.microsoft.com/v1.0/shares/u!{share_id}/driveItem/children"
    resp = requests.get(url, headers={"Authorization": f"Bearer {token}"})
    resp.raise_for_status()
    entries = resp.json().get("value", [])
    return [
        entry
        for entry in entries
        if entry.get("folder") and entry["name"].startswith("Session_")]

def _online_train_worker(job_id, share_link, token, action, language, instruction, q, cancel):
    """
    Download each Session_* folder from OneDrive (online mode) matching the given file_suffix,
    then run Transcriber/Translator/Glosser/create_columns, upload results back into OneDrive,
    and report progress to the queue.
    """
    def put(msg):
        q.put(msg)

    try:
        put("Checking for multiple sessions in OneDrive…")
        sessions_meta = _list_session_children(share_link, token)

        # If no nested Session_ folders, treat the share_link as a single session
        if not sessions_meta:
            sessions_meta = [{"webUrl": share_link, "name": None}]

        put(f"Found {len(sessions_meta)} session(s)")

        # 1) Download phase: grab all sessions first
        downloaded_sessions = []
        for entry in sessions_meta:
            if cancel.is_set():
                put("[CANCELLED during download phase]")
                break

            session_link = entry["webUrl"]
            session_name = entry.get("name") or f"Session_{len(downloaded_sessions)+1}"
            put(f"Downloading session '{session_name}'…")

            tmp_dir = tempfile.mkdtemp()
            try:
                inp, drive_id, parent_folder_id, sess_map = download_sharepoint_folder(
                    share_link=session_link,
                    temp_dir=tmp_dir,
                    access_token=token,
                    file_suffix=["annotated.xlsx"],
                )
            except Exception as e:
                put(f"  ✗ Failed to download '{session_name}': {e}. Skipping.")
                shutil.rmtree(tmp_dir, ignore_errors=True)
                continue

            # Determine actual session folder on disk
            # If root contains a subfolder named session_name, use it; else use root
            candidate = os.path.join(inp, session_name)
            session_path = candidate if os.path.isdir(candidate) else inp

            downloaded_sessions.append({
                "name": session_name,
                "tmp_dir": tmp_dir,
                "session_path": session_path,
                "drive_id": drive_id,
                "parent_folder_id": sess_map.get(session_name, parent_folder_id),
            })
            put(f"  ✓ Downloaded '{session_name}'")

        if not downloaded_sessions:
            put("[ERROR] No sessions downloaded; aborting.")
            return

        # 2) Processing & upload phase
        for sess in downloaded_sessions:
            if cancel.is_set():
                put("[CANCELLED during processing phase]")
                break

            name = sess["name"]
            path = sess["session_path"]
            drive_id = sess["drive_id"]
            parent_folder_id = sess["parent_folder_id"]

            put(f"Processing session '{name}' with action='{action}'…")
            try:
                if action == "gloss":
                    train_spacy(path, language, "cpu").process_data()
                    uploads = ["transcription.log"]
                elif action == "translate":
                    train_m2m100(path, language, instruction, "cpu").process_data()
                    uploads = []
                else:
                    put(f"  ⚠️ Unknown action '{action}', skipping.")
                    continue

                uploads.append("training_data.log")

                for fname in uploads:
                    if cancel.is_set():
                        put("[CANCELLED during uploads]")
                        break

                    local_fp = os.path.join(path, fname)
                    if not os.path.exists(local_fp):
                        put(f"  – Skipping missing file: {fname}")
                        continue

                    put(f"Uploading '{fname}' for session '{name}'…")
                    upload_file_replace_in_onedrive(
                        local_file_path=local_fp,
                        target_drive_id=drive_id,
                        parent_folder_id=parent_folder_id,
                        file_name_in_folder=fname,
                        access_token=token,
                    )
                    put(f"  ✓ Uploaded '{fname}'")

            except Exception as e:
                put(f"  [ERROR] Processing '{name}': {e}")
                put(traceback.format_exc())
            finally:
                # Clean up this session's temp dir
                shutil.rmtree(sess["tmp_dir"], ignore_errors=True)
                put(f"Cleaned up temp for '{name}'")

        put("[DONE ALL]")

    except Exception as e:
        put(f"[ERROR] {e}")
        put(traceback.format_exc())

def _offline_train_worker():
    pass