import os
import multiprocessing
import tempfile
import torch
import uuid
import json
import threading
import traceback
import requests
import time
import shutil
import queue
import msal
import base64
import requests
from zipfile import ZipFile
from pathlib import Path
from dotenv import load_dotenv
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import redirect, render
from django.http import FileResponse
from .classes.Transcriber import Transcriber
from .classes.Translator import Translator
from .classes.Glosser import Glosser
from .utils.onedrive import download_sharepoint_folder, upload_file_replace_in_onedrive
from .utils.reorder_columns import create_columns
from urllib.parse import urlencode

print("Running version:", os.getenv("APP_VERSION", "dev"))

# Load OneDrive OAuth credentials
TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
if not (TENANT_ID and CLIENT_ID and CLIENT_SECRET):
    envf = Path(__file__).parent / "materials" / "secrets.env"
    if envf.exists():
        load_dotenv(envf)
        TENANT_ID = os.getenv("TENANT_ID")
        CLIENT_ID = os.getenv("CLIENT_ID")
        CLIENT_SECRET = os.getenv("CLIENT_SECRET")
if not (TENANT_ID and CLIENT_ID and CLIENT_SECRET):
    raise ValueError("Missing OneDrive OAuth credentials")

SCOPES    = ["Files.ReadWrite.All", "User.Read"]
AUTH_URL  = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"

# In-memory store for jobs
jobs = {}

def index(request):
    version = os.getenv("APP_VERSION", "dev")
    return render(request, "index.html", {
        "app_version": version,   # ← changed from "version"
    })

# ————————————————————————————————————————————————————————————————

def _build_msal_app(cache=None):
    return msal.ConfidentialClientApplication(
        CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
        client_credential=CLIENT_SECRET,
        token_cache=cache
    )

@csrf_exempt
def get_access_token(request):
    token = request.session.get("access_token")
    return JsonResponse(
        {"access_token": token} if token else {"error": "Not authenticated"},
        status=(200 if token else 401)
    )

@csrf_exempt
def start_onedrive_auth(request):
    host = request.get_host()
    scheme = "http" if host.startswith(("localhost", "127.0.0.1")) else "https"
    redirect_uri = f"{scheme}://{host}/auth/redirect"

    msal_app = _build_msal_app()
    auth_url = msal_app.get_authorization_request_url(
        scopes=SCOPES,
        redirect_uri=redirect_uri,
        response_mode="query",
    )
    return redirect(auth_url)

@csrf_exempt
def onedrive_auth_redirect(request):
    code = request.GET.get("code")
    if not code:
        return JsonResponse({"error": "No code in callback"}, status=400)

    host = request.get_host()
    scheme = "http" if host.startswith(("localhost", "127.0.0.1")) else "https"
    redirect_uri = f"{scheme}://{host}/auth/redirect"

    msal_app = _build_msal_app()
    result = msal_app.acquire_token_by_authorization_code(
        code,
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )

    if "access_token" not in result:
        return JsonResponse({"error": "Token error", "details": result}, status=400)

    request.session["access_token"] = result["access_token"]
    return render(request, "auth_success.html", {"token": result["access_token"]})


# ————————————————————————————————————————————————————————————————
# Download endpoint: serves ZIP, then cleans up
# ————————————————————————————————————————————————————————————————
@csrf_exempt
def download_zip(request, job_id):
    print('jobs', jobs)
    job = jobs.get(job_id)
    print(f"job: {job}")
    if not job :
        print(f"job not found: {job_id}")
        return JsonResponse({"error": "No job"}, status=404)
    if not job.get("zip_path"):
        print(f"zip path not found: {job_id}")
        return JsonResponse({"error": "No zip path"}, status=404)

    zip_path = job["zip_path"]
    base_dir = job.get("base_dir")

    # Stream the file
    response = FileResponse(
        open(zip_path, "rb"),
        as_attachment=True,
        filename=f"{job_id}_results.zip"
    )

    def cleanup():
        # remove the zip file
        try:
            os.remove(zip_path)
        except OSError:
            pass
        # remove extracted folder
        if base_dir and os.path.isdir(base_dir):
            shutil.rmtree(base_dir, ignore_errors=True)
        # finally remove job entry

    # Delay cleanup slightly so the response gets sent
    threading.Thread(target=lambda: (time.sleep(2), cleanup())).start()
    return response


def upload_file_replace_in_onedrive(local_file_path, target_drive_id,
                                    parent_folder_id, file_name_in_folder,
                                    access_token):
    """
    Simple (small-file) replace-upload via Graph:
      PUT /drives/{drive-id}/items/{parent-id}:/{filename}:/content
    """
    url = (
      f"https://graph.microsoft.com/v1.0/drives/{target_drive_id}"
      f"/items/{parent_folder_id}:/{file_name_in_folder}:/content"
    )

    headers = {
        "Authorization": f"Bearer {access_token}",
        # must be octet-stream for binary
        "Content-Type": "application/octet-stream"
    }

    with open(local_file_path, "rb") as f:
        data = f.read()

    resp = requests.put(url, headers=headers, data=data)
    resp.raise_for_status()   # will surface any 4xx/5xx as exception

# ————————————————————————————————————————————————————————————————
# Worker: offline (unzipped folder already on disk)
# ————————————————————————————————————————————————————————————————
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
    except Exception as e:
        print(f"Error in offline worker: {e}")
        put(f"[ERROR] {e}")
        put(traceback.format_exc())
    finally:
        put("[DONE ALL]")
        jobs.pop(job_id, None)

# ————————————————————————————————————————————————————————————————
# Worker: online (OneDrive)
# ————————————————————————————————————————————————————————————————
def _list_session_children(share_link: str, token: str):
    """
    Uses Microsoft Graph to list the children of a shared folder,
    returning only those named 'Session_*'.
    """
    # Encode the share_link into a Graph-shareable ID (u! format)
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
        # 1) list session children
        put("Checking for multiple sessions in OneDrive…")
        sessions_meta = _list_session_children(base_dir, token)

        # 2) if no children, treat the link itself as one session
        if not sessions_meta:
            sessions_meta = [{"webUrl": base_dir}]
        
        print(f"Found {len(sessions_meta)} sessions")
        put(f"Found {len(sessions_meta)} sessions")
        for entry in sessions_meta:
            if cancel.is_set():
                put("[CANCELLED]")
                break

            session_link = entry.get("webUrl")
            # download the folder and get sess_map
            put(f"Downloading from onedrive")
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
            # determine real name: first from Graph metadata, else from sess_map keys
            put(f"Processing session: {session_name}")

            # locate the actual session folder on disk
            # download_sharepoint_folder unpacks to a folder named by the real folder
            session_path = os.path.join(inp, session_name)
            if not os.path.isdir(session_path):
                # fallback if download flattened it into inp itself
                session_path = inp

            # do the work
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

            # upload each result
            for fname in uploads:
                if cancel.is_set():
                    put("[CANCELLED]")
                    break
                local_fp = os.path.join(session_path, fname)
                if not os.path.exists(local_fp):
                    put(f"Skipping missing: {fname}")
                    continue
                put(f"Uploading {fname} for {session_name}")
                # use our fixed helper
                upload_file_replace_in_onedrive(
                    local_file_path=local_fp,
                    target_drive_id=drive_id,
                    parent_folder_id=sess_map.get(session_name, ""),
                    file_name_in_folder=fname,
                    access_token=token
                )

            shutil.rmtree(tmp_dir, ignore_errors=True)
            print(f"Uploaded {fname} for {session_name}")
            put(f"[DONE UPLOADED] {session_name}")

    except Exception as e:
        print(f"Error in online worker: {e}")
        put(f"[ERROR] {e}")
        put(traceback.format_exc())
    finally:
        put("[DONE ALL]")
        jobs.pop(job_id, None)



# ————————————————————————————————————————————————————————————————
# Kick off the appropriate worker
# ————————————————————————————————————————————————————————————————
@csrf_exempt
def process(request):
    if request.method != "POST":
        return JsonResponse({"error": "Use POST"}, status=400)

    # new job
    job_id = str(uuid.uuid4())
    q      = multiprocessing.Queue()
    cancel = multiprocessing.Event()
    jobs[job_id] = {"queue": q, "cancel": cancel, "zip_path": None}

    action = request.POST.get("action")
    language = request.POST.get("language")
    instruction = request.POST.get("instruction")
    token = request.session.get("access_token") or request.POST.get("access_token")

    if not language:
        q.put("[ERROR] Missing language")
        return JsonResponse({"job_id": job_id})

    # offline via client ZIP
    if 'zipfile' in request.FILES:
        z = request.FILES['zipfile']
        tmp_dir = tempfile.mkdtemp()
        zip_path = Path(tmp_dir) / "upload.zip"
        with open(zip_path, "wb") as f:
            for chunk in z.chunks():
                f.write(chunk)
        with ZipFile(zip_path, 'r') as archive:
            archive.extractall(tmp_dir)
        os.remove(zip_path)

        worker = _offline_worker
        args = (job_id, tmp_dir, action, language, instruction, q, cancel)

    else:
        # online via OneDrive
        base_dir = request.POST.get("base_dir")
        if not (base_dir and token):
            return JsonResponse({"error": "Missing base_dir or token"}, status=400)
        worker = _online_worker
        args   = (job_id, base_dir, token, action, language, instruction, q, cancel)

    p = multiprocessing.Process(target=worker, args=args, daemon=True)
    p.start()
    jobs[job_id]["process"] = p

    return JsonResponse({"job_id": job_id})

# ————————————————————————————————————————————————————————————————
# Server‐Sent Events stream
# ————————————————————————————————————————————————————————————————
@csrf_exempt
def stream(request, job_id):
    job = jobs.get(job_id)
    if not job:
        return JsonResponse({"error": "Unknown job_id"}, status=404)

    q = job["queue"]
    def event_stream():
        # flush backlog
        while True:
            try:
                yield f"data: {q.get_nowait()}\n\n"
            except queue.Empty:
                break
        # stream until done
        while True:
            line = q.get()
            if line == "[DONE ALL]":
                yield f"data: [DONE ALL]\n\n"
                break

            elif line.startswith("[ZIP PATH] "):
                zip_path = line[len("[ZIP PATH] "):].strip()
                job["zip_path"] = zip_path

            else:
                yield f"data: {line}\n\n"

    return StreamingHttpResponse(event_stream(), content_type="text/event-stream")

# ————————————————————————————————————————————————————————————————
@csrf_exempt
def cancel(request):
    body = json.loads(request.body)
    jid  = body.get("job_id")
    job  = jobs.get(jid)
    if not job:
        return JsonResponse({"error": "Unknown job_id"}, status=404)
    q = job["queue"]
    q.put("[CANCELLED]")
    q.put("[DONE ALL]")
    proc = job.get("process")
    if proc and proc.is_alive():
        proc.terminate()
    jobs.pop(jid, None)
    return JsonResponse({"status": "cancelled"})    

def terms_view(request):
    return render(request, "terms.html")

def privacy_view(request):
    return render(request, "privacy.html")
