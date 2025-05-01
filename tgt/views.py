import uuid
import torch
import threading
import io
import tempfile
import os
from queue import Queue, Empty
from contextlib import redirect_stdout, redirect_stderr
from django.http import JsonResponse, StreamingHttpResponse, HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.clickjacking import xframe_options_exempt
from urllib.parse import urlencode
import requests

from .classes.Transcriber import Transcriber
from .classes.Translator import Translator
from .classes.Glosser import Glosser
from .utils.onedrive import download_sharepoint_folder, upload_file_replace_in_onedrive

TENANT_ID = '7ef3035c-bf11-463a-ab3b-9a9a4ac82500'
CLIENT_ID = '58c0d230-141d-4a30-905e-fd63e331e5ea'
CLIENT_SECRET = 'sY38Q~CknTafzzQQ37TS9QTKD256Z3aovopynbWZ'

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["Files.ReadWrite.All", "User.Read"]

jobs = {}  # job_id -> {"queue": Queue(), "finished": bool, "cancelled": bool}

def get_redirect_uri(request):
    host = request.get_host()
    
    # Explicitly detect local development
    if host.startswith("localhost") or host.startswith("127.0.0.1"):
        scheme = "http"
    else:
        scheme = "https"

    return f"{scheme}://{host}/auth/redirect"

@csrf_exempt
def get_access_token(request):
    token = request.session.get("access_token")
    if token:
        return JsonResponse({"access_token": token})
    return JsonResponse({"error": "Not authenticated"}, status=401)

def home(request):
    return render(request, 'index.html')


@csrf_exempt
def start_onedrive_auth(request):
    redirect_uri = get_redirect_uri(request)
    auth_url = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": " ".join(SCOPES),
        "response_mode": "query",
    }
    return redirect(f"{auth_url}?{urlencode(params)}")

@csrf_exempt
def onedrive_auth_redirect(request):
    code = request.GET.get("code")
    if not code:
        return JsonResponse({"error": "No code in callback"}, status=400)

    redirect_uri = get_redirect_uri(request)
    token_url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope": " ".join(SCOPES),
        "code": code,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }

    response = requests.post(token_url, data=data)
    token_data = response.json()

    if "access_token" not in token_data:
        return JsonResponse({"error": "Failed to get token", "details": token_data}, status=400)

    request.session['access_token'] = token_data['access_token']
    return render(request, 'auth_success.html', {"token": token_data["access_token"]})


@csrf_exempt
def process(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=400)

    onedrive_link = request.POST.get('base_dir')
    language = request.POST.get('language')
    action = request.POST.get('action')
    instruction = request.POST.get('instruction')

    if not onedrive_link:
        return JsonResponse({'error': 'Missing base_dir or OneDrive link'}, status=400)

    access_token = request.session.get("access_token")
    if not access_token:
        return JsonResponse({'error': 'Missing access token'}, status=403)

    job_id = str(uuid.uuid4())
    q = Queue()
    jobs[job_id] = {"queue": q, "finished": False, "cancelled": False}

    def log_worker(access_token):
        class QueueWriter(io.TextIOBase):
            def write(self, txt):
                for line in txt.rstrip().splitlines():
                    q.put(line)
            def flush(self): pass

        writer = QueueWriter()

        try:
            with redirect_stdout(writer), redirect_stderr(writer):
                temp_dir = tempfile.mkdtemp()

                input_dir, drive_id, parent_id, session_folder_id_map = download_sharepoint_folder(
                    share_link=onedrive_link,
                    temp_dir=temp_dir,
                    access_token=access_token
                )

                session_folders = []
                first_level_entries = os.listdir(input_dir)

                if all(entry.startswith("Session_") for entry in first_level_entries):
                    for session_folder_name in first_level_entries:
                        session_folder_path = os.path.join(input_dir, session_folder_name)
                        if os.path.isdir(session_folder_path):
                            session_folders.append(session_folder_path)
                else:
                    for collection_folder in first_level_entries:
                        collection_path = os.path.join(input_dir, collection_folder)
                        if not os.path.isdir(collection_path):
                            continue
                        for session_folder_name in os.listdir(collection_path):
                            session_folder_path = os.path.join(collection_path, session_folder_name)
                            if os.path.isdir(session_folder_path) and session_folder_name.startswith("Session_"):
                                session_folders.append(session_folder_path)

                for session_folder_path in session_folders:
                    if jobs[job_id].get("cancelled"):
                        q.put("[CANCELLED]")
                        break

                    session_folder_name = os.path.basename(session_folder_path)
                    print(f"Processing session: {session_folder_name}")
                    files_to_upload = ["trials_and_sessions_annotated.xlsx"]

                    if action == 'transcribe':
                        transcriber = Transcriber(session_folder_path, language, 'cuda' if torch.cuda.is_available() else 'cpu')
                        transcriber.process_data(verbose=True)
                        files_to_upload.append("transcription.log")
                    elif action == 'translate':
                        translator = Translator(session_folder_path, language, instruction, 'cuda' if torch.cuda.is_available() else 'cpu')
                        translator.process_data(verbose=True)
                        files_to_upload.append("translation.log")
                    elif action == 'gloss':
                        glosser = Glosser(session_folder_path, language, instruction)
                        glosser.process_data()

                    for file_name in files_to_upload:
                        local_file = os.path.join(session_folder_path, file_name)
                        if not os.path.exists(local_file):
                            print(f"Skipping upload, file not found: {file_name}")
                            continue
                        print(f"Uploading file: {file_name}")
                        session_folder_id = session_folder_id_map.get(session_folder_name)
                        if session_folder_id:
                            upload_file_replace_in_onedrive(
                                local_file_path=local_file,
                                target_drive_id=drive_id,
                                parent_folder_id=session_folder_id,
                                file_name_in_folder=file_name,
                                access_token=access_token
                            )
                        else:
                            print(f"Skipping upload: session folder {session_folder_name} not found in ID map.")

                    q.put(f"[DONE UPLOADED] {session_folder_name}")

                if not jobs[job_id].get("cancelled"):
                    q.put("[DONE ALL]")

        except Exception as e:
            q.put(f"[ERROR] {e}")
        finally:
            jobs[job_id]["finished"] = True

    threading.Thread(target=log_worker, args=(access_token,), daemon=True).start()
    return JsonResponse({'job_id': job_id})

def logs(request, job_id):
    if job_id not in jobs:
        return HttpResponse("Unknown job ID", status=404)

    def event_stream():
        q = jobs[job_id]['queue']
        while True:
            try:
                line = q.get(timeout=5)
                yield f"data: {line}\n\n"
                if line in ("[DONE ALL]", "[CANCELLED]") or line.startswith("[ERROR]"):
                    break
            except Empty:
                yield "data: [PING]\n\n"

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response

@csrf_exempt
def cancel(request, job_id):
    if request.method == 'POST':
        if job_id in jobs:
            jobs[job_id]["cancelled"] = True
            return JsonResponse({"status": "cancelling"})
        return JsonResponse({"error": "Unknown job ID"}, status=404)
    return JsonResponse({'error': 'Invalid request method'}, status=400)
