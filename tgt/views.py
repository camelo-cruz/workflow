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
    return render(request, "index.html")

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
        put(f"[ERROR] {e}")
        put(traceback.format_exc())
    finally:
        put("[DONE ALL]")
        jobs.pop(job_id, None)

# ————————————————————————————————————————————————————————————————
# Worker: online (OneDrive)
# ————————————————————————————————————————————————————————————————
def _online_worker(job_id, base_dir, token, action, language, instruction, q, cancel):
    def put(msg): q.put(msg)
    try:
        put("Downloading from OneDrive…")
        tmp_dir = tempfile.mkdtemp()
        try:
            inp, drive_id, _, sess_map = download_sharepoint_folder(
                share_link=base_dir, temp_dir=tmp_dir, access_token=token
            )
        except Exception as e:
            put(f"[ERROR] Failed to download: {str(e)}")
            put(traceback.format_exc())
            return

        sessions = [
            os.path.join(root, subdir)
            for root, dirs, _ in os.walk(inp)
            for subdir in dirs if subdir.startswith("Session_")
        ]

        for session in sessions:
            if cancel.is_set():
                put("[CANCELLED]")
                break
            name = os.path.basename(session)
            put(f"Processing session: {name}")

            uploads = []
            if action == "transcribe":
                Transcriber(session, language, "cpu").process_data(verbose=True)
                uploads = ["transcription.log"]
            elif action == "translate":
                Translator(session, language, instruction, "cpu").process_data(verbose=True)
                uploads = ["translation.log"]
            elif action == "gloss":
                Glosser(session, language, instruction).process_data()
            elif action == "create columns":
                create_columns(session, language)

            uploads.append("trials_and_sessions_annotated.xlsx")
            for file_name in uploads:
                if cancel.is_set():
                    put("[CANCELLED]")
                    break
                file_path = os.path.join(session, file_name)
                if not os.path.exists(file_path):
                    put(f"Skipping missing: {file_name}")
                    continue
                put(f"Uploading file: {file_name}")
                upload_file_replace_in_onedrive(
                    local_file_path=file_path,
                    target_drive_id=drive_id,
                    parent_folder_id=sess_map.get(name, ""),
                    file_name_in_folder=file_name,
                    access_token=token
                )
            put(f"[DONE UPLOADED] {name}")
    except Exception as e:
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
