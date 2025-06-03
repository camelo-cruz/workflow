# routers/jobs.py

import os
import uuid
import multiprocessing
import traceback
import requests
import shutil
import queue

import base64
from zipfile import ZipFile
from pathlib import Path
import tempfile

import msal
from fastapi import APIRouter, Request, Form, UploadFile, File, Body, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse, FileResponse
from fastapi.templating import Jinja2Templates

from classes.Transcriber import Transcriber
from classes.Translator import Translator
from classes.Glosser import Glosser
from utils.onedrive import download_sharepoint_folder, upload_file_replace_in_onedrive
from utils.reorder_columns import create_columns

# Set up Jinja2 templates
templates = Jinja2Templates(directory="templates")
router = APIRouter()

# In‐memory store for jobs
jobs: dict[str, dict] = {}

# Load OneDrive OAuth credentials
TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
if not (TENANT_ID and CLIENT_ID and CLIENT_SECRET):
    raise ValueError("Missing OneDrive OAuth credentials")

SCOPES    = ["Files.ReadWrite.All", "User.Read"]
AUTH_URL  = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"


def _build_msal_app(cache=None):
    return msal.ConfidentialClientApplication(
        CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
        client_credential=CLIENT_SECRET,
        token_cache=cache
    )


@router.get("/")
async def index(request: Request):
    version = os.getenv("APP_VERSION", "dev")
    return templates.TemplateResponse("index.html", {"request": request, "app_version": version})


@router.get("/auth/start")
async def start_onedrive_auth(request: Request):
    host = request.headers.get("host")
    scheme = "http" if host.startswith(("localhost", "127.0.0.1")) else "https"
    redirect_uri = f"{scheme}://{host}/auth/redirect"

    msal_app = _build_msal_app()
    auth_url = msal_app.get_authorization_request_url(
        scopes=SCOPES,
        redirect_uri=redirect_uri,
        response_mode="query",
    )
    return RedirectResponse(url=auth_url, status_code=302)


@router.get("/auth/redirect")
async def onedrive_auth_redirect(request: Request):
    code = request.query_params.get("code")
    if not code:
        return JSONResponse({"error": "No code in callback"}, status_code=400)

    host = request.headers.get("host")
    scheme = "http" if host.startswith(("localhost", "127.0.0.1")) else "https"
    redirect_uri = f"{scheme}://{host}/auth/redirect"

    msal_app = _build_msal_app()
    result = msal_app.acquire_token_by_authorization_code(
        code,
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )

    if "access_token" not in result:
        return JSONResponse({"error": "Token error", "details": result}, status_code=400)

    # Return the access token to the frontend (e.g., via rendered template)
    return templates.TemplateResponse(
        "auth_success.html",
        {"request": request, "token": result["access_token"]}
    )


# ────────────────────────────────────────────────────────────────────────────────
# ───────────────────────────────── Download ZIP endpoint ─────────────────────────────────
# ────────────────────────────────────────────────────────────────────────────────
@router.get("/jobs/{job_id}/download")
async def download_zip(job_id: str, background_tasks: BackgroundTasks):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="No job")
    zip_path = job.get("zip_path")
    if not zip_path:
        raise HTTPException(status_code=404, detail="No zip path")

    base_dir = job.get("base_dir")

    def cleanup():
        try:
            os.remove(zip_path)
        except OSError:
            pass
        if base_dir and os.path.isdir(base_dir):
            shutil.rmtree(base_dir, ignore_errors=True)
        jobs.pop(job_id, None)

    background_tasks.add_task(cleanup)

    return FileResponse(
        path=zip_path,
        media_type="application/zip",
        filename=f"{job_id}_results.zip"
    )


# ────────────────────────────────────────────────────────────────────────────────
# ────────────────────────────────── Workers ─────────────────────────────────────
# ────────────────────────────────────────────────────────────────────────────────
def _offline_worker(job_id, base_dir, action, language, instruction, q, cancel):
    def put(msg): q.put(msg)
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
            elif action == "create columns":
                create_columns(session, language)

        # create ZIP of entire folder
        zip_path = Path(tempfile.gettempdir()) / f"{job_id}_output.zip"
        with ZipFile(zip_path, "w") as z:
            for root, _, files in os.walk(base_dir):
                for file in files:
                    if file in ("trials_and_sessions_annotated.xlsx", "transcription.log", "translation.log"):
                        full = os.path.join(root, file)
                        rel = os.path.relpath(full, base_dir)
                        z.write(full, arcname=rel)

        put(f"[ZIP PATH] {zip_path}")
        jobs[job_id]["zip_path"] = str(zip_path)
        jobs[job_id]["base_dir"] = base_dir

    except Exception as e:
        put(f"[ERROR] {e}")
        put(traceback.format_exc())
    finally:
        put("[DONE ALL]")
        jobs.pop(job_id, None)


def _list_session_children(share_link: str, token: str):
    share_id = base64.urlsafe_b64encode(share_link.encode()).decode().rstrip("=")
    url = f"https://graph.microsoft.com/v1.0/shares/u!{share_id}/driveItem/children"
    resp = requests.get(url, headers={"Authorization": f"Bearer {token}"})
    resp.raise_for_status()
    entries = resp.json().get("value", [])
    return [
        entry for entry in entries
        if entry.get("folder") and entry["name"].startswith("Session_")
    ]


def _online_worker(job_id, base_dir, token, action, language, instruction, q, cancel):
    def put(msg): q.put(msg)
    try:
        put("Checking for multiple sessions in OneDrive…")
        sessions_meta = _list_session_children(base_dir, token)

        if not sessions_meta:
            sessions_meta = [{"webUrl": base_dir}]

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
                    access_token=token
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
                Transcriber(session_path, language, "cpu").process_data(verbose=True)
                uploads = ["transcription.log"]
            elif action == "translate":
                Translator(session_path, language, instruction, "cpu").process_data(verbose=True)
                uploads = ["translation.log"]
            elif action == "gloss":
                Glosser(session_path, language, instruction).process_data()
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
                    access_token=token
                )

            shutil.rmtree(tmp_dir, ignore_errors=True)
            put(f"[DONE UPLOADED] {session_name}")

    except Exception as e:
        put(f"[ERROR] {e}")
        put(traceback.format_exc())
    finally:
        put("[DONE ALL]")
        jobs.pop(job_id, None)


# ────────────────────────────────────────────────────────────────────────────────
# ───────────────────────────────── process ────────────────────────────────────────
# ────────────────────────────────────────────────────────────────────────────────
@router.post("/jobs/process")
async def process(
    request: Request,
    action: str = Form(...),
    language: str = Form(...),
    instruction: str | None = Form(None),
    access_token: str | None = Form(None),
    zipfile: UploadFile | None = File(None),
    base_dir: str | None = Form(None),
):
    job_id = str(uuid.uuid4())
    q = multiprocessing.Queue()
    cancel = multiprocessing.Event()

    token = access_token  # take token from form data
    jobs[job_id] = {
        "queue": q,
        "cancel": cancel,
        "zip_path": None,
        "token": token
    }

    if not language:
        q.put("[ERROR] Missing language")
        return {"job_id": job_id}

    if zipfile is not None:
        # Offline: save uploaded zip, extract
        tmp_dir = tempfile.mkdtemp()
        zip_path = Path(tmp_dir) / "upload.zip"
        contents = await zipfile.read()
        with open(zip_path, "wb") as f:
            f.write(contents)
        with ZipFile(zip_path, "r") as archive:
            archive.extractall(tmp_dir)
        os.remove(zip_path)

        worker = _offline_worker
        args = (job_id, tmp_dir, action, language, instruction, q, cancel)
        jobs[job_id]["base_dir"] = tmp_dir

    else:
        # Online: need base_dir (share link) + token
        if not (base_dir and token):
            raise HTTPException(status_code=400, detail="Missing base_dir or token")
        worker = _online_worker
        args = (job_id, base_dir, token, action, language, instruction, q, cancel)
        # no base_dir folder to store in-memory

    p = multiprocessing.Process(target=worker, args=args, daemon=True)
    p.start()
    jobs[job_id]["process"] = p

    return {"job_id": job_id}


# ────────────────────────────────────────────────────────────────────────────────
# ───────────────────────────────── stream ────────────────────────────────────────
# ────────────────────────────────────────────────────────────────────────────────
@router.get("/jobs/{job_id}/stream")
async def stream(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown job_id")

    q: multiprocessing.Queue = job["queue"]

    def event_generator():
        # flush backlog
        while True:
            try:
                line = q.get_nowait()
            except queue.Empty:
                break
            if line == "[DONE ALL]":
                yield b"data: [DONE ALL]\n\n"
                return
            elif line.startswith("[ZIP PATH] "):
                zip_path = line[len("[ZIP PATH] "):].strip()
                job["zip_path"] = zip_path
            else:
                yield f"data: {line}\n\n".encode("utf-8")

        # stream until done
        while True:
            line = q.get()
            if line == "[DONE ALL]":
                yield b"data: [DONE ALL]\n\n"
                break
            elif line.startswith("[ZIP PATH] "):
                zip_path = line[len("[ZIP PATH] "):].strip()
                job["zip_path"] = zip_path
            else:
                yield f"data: {line}\n\n".encode("utf-8")

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ────────────────────────────────────────────────────────────────────────────────
# ───────────────────────────────── cancel ────────────────────────────────────────
# ────────────────────────────────────────────────────────────────────────────────
@router.post("/jobs/cancel")
async def cancel_job(payload: dict = Body(...)):
    jid = payload.get("job_id")
    job = jobs.get(jid)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown job_id")
    q: multiprocessing.Queue = job["queue"]
    q.put("[CANCELLED]")
    q.put("[DONE ALL]")
    proc = job.get("process")
    if proc and proc.is_alive():
        proc.terminate()
    jobs.pop(jid, None)
    return {"status": "cancelled"}


# ────────────────────────────────────────────────────────────────────────────────
# ────────────────────────── terms / privacy ──────────────────────────────────────
# ────────────────────────────────────────────────────────────────────────────────
@router.get("/terms")
async def terms_view(request: Request):
    return templates.TemplateResponse("terms.html", {"request": request})


@router.get("/privacy")
async def privacy_view(request: Request):
    return templates.TemplateResponse("privacy.html", {"request": "request"})
