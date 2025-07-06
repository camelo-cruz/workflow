import os
import tempfile
import traceback
import shutil
import queue
import requests
import base64

from zipfile import ZipFile
from pathlib import Path

from inference.data_processors.transcribe import Transcriber
from inference.data_processors.translate import Translator
from inference.data_processors.gloss import Glosser
from inference.data_processors.transliterate import Transliterator

from utils.onedrive import download_sharepoint_folder, upload_file_replace_in_onedrive
from utils.reorder_columns import create_columns


def _offline_worker(job_id, base_dir, action, language, instruction, q, cancel):
    """
    Process an uploaded ZIP (offline mode).  Walk through all Session_* folders,
    run Transcriber/Translator/Glosser/create_columns, then zip up the results.
    """
    def put(msg): 
        q.put(msg)

    try:
        put("Processing uploaded files…")

        # find all Session_* directories
        sessions = [
            os.path.join(root, subdir)
            for root, dirs, _ in os.walk(base_dir)
            for subdir in dirs if subdir.startswith("Session_")
        ]

        for session in sessions:
            if cancel.is_set():
                put("[CANCELLED]")
                break

            name = os.path.basename(session)
            put(f"Processing session: {name}")

            if action == "transcribe":
                Transcriber(session, language, "cpu").process_data(verbose=True)
            elif action == "translate":
                Translator(session, language, instruction, "cpu").process_data(verbose=True)
            elif action == "gloss":
                Glosser(session, language, instruction).process_data()
            elif action == "transliterate":
                Transliterator(session, language, instruction).process_data(verbose=True)
            elif action == "create columns":
                create_columns(session, language)

        # create ZIP of entire folder
        zip_path = Path(tempfile.gettempdir()) / f"{job_id}_output.zip"
        with ZipFile(zip_path, "w") as z:
            for root, _, files in os.walk(base_dir):
                for file in files:
                    if file in (
                        "trials_and_sessions_annotated.xlsx",
                        "transcription.log",
                        "translation.log",
                    ):
                        full = os.path.join(root, file)
                        rel = os.path.relpath(full, base_dir)
                        z.write(full, arcname=rel)

        put(f"[ZIP PATH] {zip_path}")
        # The caller (jobs.py) will write into jobs[job_id]["zip_path"] and ["base_dir"]
    except Exception as e:
        put(f"[ERROR] {e}")
        put(traceback.format_exc())
    finally:
        put("[DONE ALL]")


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
        if entry.get("folder") and entry["name"].startswith("Session_")
    ]


def _online_worker(job_id, share_link, token, action, language, instruction, translationModel, glossingModel, q, cancel):
    """
    Download each Session_* folder from OneDrive (online mode), run Transcriber/Translator/Glosser/create_columns,
    upload results back into OneDrive, and report progress to the queue.
    """
    def put(msg):
        q.put(msg)

    try:
        put("Checking for multiple sessions in OneDrive…")
        sessions_meta = _list_session_children(share_link, token)

        if not sessions_meta:
            # if there are no nested Session_ folders, assume share_link points directly to a single Session
            sessions_meta = [{"webUrl": share_link}]

        put(f"Found {len(sessions_meta)} sessions")
        for entry in sessions_meta:
            if cancel.is_set():
                put("[CANCELLED]")
                break

            session_link = entry.get("webUrl")
            put(f"Downloading from OneDrive")
            tmp_dir = tempfile.mkdtemp()
            try:
                inp, drive_id, _, sess_map = download_sharepoint_folder(
                    share_link=session_link,
                    temp_dir=tmp_dir,
                    access_token=token,
                )
            except Exception as e:
                put(f"Failed to download session: {e}. Will skip.")
                shutil.rmtree(tmp_dir, ignore_errors=True)
                continue

            session_name = entry.get("name") or next(iter(sess_map.keys()), Path(inp).name)
            put(f"Processing session: {session_name}")

            session_path = os.path.join(inp, session_name)
            if not os.path.isdir(session_path):
                session_path = inp

            uploads = []
            if action == "transcribe":
                Transcriber(session_path, language, "cpu").process_data()
                uploads = ["transcription.log"]
            elif action == "translate":
                Translator(session_path, language, instruction, "cpu").process_data()
                uploads = ["translation.log"]
            elif action == "gloss":
                Glosser(session_path, language, instruction, glossingModel, translationModel).process_data()
            elif action == "transliterate":
                Transliterator(session_path, language, instruction).process_data()
            elif action == "create columns":
                create_columns(session_path, language)

            uploads.append("trials_and_sessions_annotated.xlsx")

            for fname in uploads:
                if cancel.is_set():
                    put("[CANCELLED]")
                    break
                local_fp = os.path.join(session_path, fname)
                if not os.path.exists(local_fp):
                    put(f"Skipping missing: {fname}")
                    continue

                put(f"Uploading {fname} for {session_name}")
                upload_file_replace_in_onedrive(
                    local_file_path=local_fp,
                    target_drive_id=drive_id,
                    parent_folder_id=sess_map.get(session_name, ""),
                    file_name_in_folder=fname,
                    access_token=token,
                )

            shutil.rmtree(tmp_dir, ignore_errors=True)
            put(f"[DONE UPLOADED] {session_name}")

    except Exception as e:
        put(f"[ERROR] {e}")
        put(traceback.format_exc())
    finally:
        put("[DONE ALL]")
