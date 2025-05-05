import os
import multiprocessing
import tempfile
import torch
import uuid
import json
import requests
import time
from pathlib import Path
from dotenv import load_dotenv
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import redirect, render
from .classes.Transcriber import Transcriber
from .classes.Translator import Translator
from .classes.Glosser import Glosser
from .utils.onedrive import download_sharepoint_folder, upload_file_replace_in_onedrive
from .utils.reorder_columns import process_columns
from urllib.parse import urlencode
import queue

print("Running version:", os.getenv("APP_VERSION", "dev"))

# Load OneDrive OAuth credentials
TENANT_ID     = os.getenv("TENANT_ID")
CLIENT_ID     = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
if not (TENANT_ID and CLIENT_ID and CLIENT_SECRET):
    envf = Path(__file__).parent / "materials" / "secrets.env"
    if envf.exists():
        load_dotenv(envf)
        TENANT_ID     = os.getenv("TENANT_ID")
        CLIENT_ID     = os.getenv("CLIENT_ID")
        CLIENT_SECRET = os.getenv("CLIENT_SECRET")
if not (TENANT_ID and CLIENT_ID and CLIENT_SECRET):
    raise ValueError("Missing OneDrive OAuth credentials")

SCOPES    = ["Files.ReadWrite.All", "User.Read"]
AUTH_URL  = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"

# In-memory store for jobs
jobs = {}

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
    scheme = "http" if host.startswith(("localhost","127.0.0.1")) else "https"
    redirect_uri = f"{scheme}://{host}/auth/redirect"
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": " ".join(SCOPES),
        "response_mode": "query",
    }
    return redirect(f"{AUTH_URL}?{urlencode(params)}")

@csrf_exempt
def onedrive_auth_redirect(request):
    code = request.GET.get("code")
    if not code:
        return JsonResponse({"error":"No code in callback"}, status=400)
    host = request.get_host()
    scheme = "http" if host.startswith(("localhost","127.0.0.1")) else "https"
    redirect_uri = f"{scheme}://{host}/auth/redirect"
    resp = requests.post(TOKEN_URL, data={
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope":         " ".join(SCOPES),
        "code":          code,
        "redirect_uri":  redirect_uri,
        "grant_type":    "authorization_code",
    })
    data = resp.json()
    if "access_token" not in data:
        return JsonResponse({"error":"Failed to get token","details":data}, status=400)
    request.session['access_token'] = data["access_token"]
    return render(request, "auth_success.html", {"token": data["access_token"]})


def _worker(job_id, base_dir, token, action, language, instruction, q, cancel):
    """
    Worker process: downloads data, processes sessions, uploads results, and respects cancel event.
    """
    def put(line):
        q.put(line)

    try:
        put("Downloading from OneDrive…")
        tmp = tempfile.mkdtemp()
        inp, drive_id, _, sess_map = download_sharepoint_folder(
            share_link=base_dir, temp_dir=tmp, access_token=token
        )
        # gather session directories
        sessions = []
        for root, dirs, _ in os.walk(inp):
            for d in dirs:
                if d.startswith("Session_"):
                    sessions.append(os.path.join(root, d))

        for sess in sessions:
            if cancel.is_set():
                put("[CANCELLED]")
                break

            name = os.path.basename(sess)
            put(f"Processing session: {name}")

            # Choose runner based on action
            if action == "transcribe":
                runner = Transcriber(sess, language, "cuda" if torch.cuda.is_available() else "cpu")
                runner.process_data(verbose=True)
                ups = ["transcription.log"]
            elif action == "translate":
                runner = Translator(sess, language, instruction, "cuda" if torch.cuda.is_available() else "cpu")
                runner.process_data(verbose=True)
                ups = ["translation.log"]
            elif action == "gloss":
                g = Glosser(sess, language, instruction)
                g.process_data()
                ups = []
            elif action == "create columns":
                process_columns(sess, language)
                ups = []
            else:
                ups = []

            ups.append("trials_and_sessions_annotated.xlsx")
            print(f"Files to upload: {ups}")
            for fn in ups:
                if cancel.is_set():
                    put("[CANCELLED]")
                    break
                path = os.path.join(sess, fn)
                if not os.path.exists(path):
                    put(f"Skipping missing file: {fn}")
                    continue
                put(f"Uploading file: {fn}")
                upload_file_replace_in_onedrive(
                    local_file_path=path,
                    target_drive_id=drive_id,
                    parent_folder_id=sess_map.get(name, ""),
                    file_name_in_folder=fn,
                    access_token=token
                )
            put(f"[DONE UPLOADED] {name}")

        if not cancel.is_set():
            put("[DONE ALL]")

    except Exception as e:
        put(f"[ERROR] {e}")


@csrf_exempt
def process(request):
    if request.method != "POST":
        return JsonResponse({"error": "Use POST"}, status=400)
    base_dir    = request.POST.get("base_dir")
    token       = request.session.get("access_token") or request.POST.get("access_token")
    action      = request.POST.get("action")
    language    = request.POST.get("language")
    instruction = request.POST.get("instruction")
    if not (base_dir and token):
        return JsonResponse({"error": "Missing params"}, status=400)

    job_id = str(uuid.uuid4())
    # Create inter-process queue and cancel event
    q      = multiprocessing.Queue()
    cancel = multiprocessing.Event()
    jobs[job_id] = {"queue": q, "cancel": cancel, "finished": False}

    # Start worker in separate process
    p = multiprocessing.Process(
        target=_worker,
        args=(job_id, base_dir, token, action, language, instruction, q, cancel),
        daemon=True
    )
    p.start()
    jobs[job_id]["process"] = p

    return JsonResponse({"job_id": job_id})


@csrf_exempt
def stream(request, job_id):
    if job_id not in jobs:
        return JsonResponse({"error": "Unknown job_id"}, status=404)
    job = jobs[job_id]
    q = job["queue"]

    def event_stream():
        # 1) Drain any backlog
        while True:
            try:
                line = q.get_nowait()
                yield f"data: {line}\n\n"
            except queue.Empty:
                break
        # 2) Stream until DONE ALL
        while True:
            line = q.get()  # blocks
            if line == "[DONE ALL]":
                yield "event: done\n"
                yield "data: ok\n\n"
                break
                jobs.pop(jid, None)
            else:
                yield f"data: {line}\n\n"

    resp = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    resp["Cache-Control"]     = "no-cache"
    resp["X-Accel-Buffering"] = "no"
    return resp


@csrf_exempt
def cancel(request):
    body = json.loads(request.body.decode())
    jid  = body.get("job_id")
    job  = jobs.get(jid)
    if not job:
        return JsonResponse({"error": "Unknown job_id"}, status=404)

    q    = job["queue"]
    proc = job.get("process")

    # Notify client, then terminate
    q.put("[CANCELLED]")
    q.put("[DONE ALL]")

    if proc and proc.is_alive():
        proc.terminate()
        proc.join(timeout=1)

    # Clean up
    jobs.pop(jid, None)

    return JsonResponse({"status": "cancelled"})
