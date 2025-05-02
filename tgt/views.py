import io
import sys
import os
import tempfile
import torch
import threading
from contextlib import redirect_stdout, redirect_stderr
from urllib.parse import urlencode
from dotenv import load_dotenv 

import requests
from django.http import JsonResponse, StreamingHttpResponse, HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt

from .classes.Transcriber import Transcriber
from .classes.Translator  import Translator
from .classes.Glosser      import Glosser
from .utils.onedrive       import download_sharepoint_folder, upload_file_replace_in_onedrive

# Try loading from environment first (used in Hugging Face Spaces)
TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

# If not found, try loading from local .env file for local development
if not TENANT_ID or not CLIENT_ID or not CLIENT_SECRET:
    base_path = os.path.dirname(os.path.abspath(__file__))
    secrets_path = os.path.join(base_path, 'materials', 'secrets.env')
    
    if not TENANT_ID:
        if os.path.exists(secrets_path):
            load_dotenv(secrets_path, override=True)
            TENANT_ID = os.getenv("TENANT_ID")
    if not CLIENT_ID:
        if os.path.exists(secrets_path):
            load_dotenv(secrets_path, override=True)
            CLIENT_ID = os.getenv("CLIENT_ID")
    if not CLIENT_SECRET:
        if os.path.exists(secrets_path):
            load_dotenv(secrets_path, override=True)
            CLIENT_SECRET = os.getenv("CLIENT_SECRET")

if not TENANT_ID or not CLIENT_ID or not CLIENT_SECRET:
    raise ValueError("Missing TENANT_ID, CLIENT_ID, or CLIENT_SECRET. Please set them in the environment or in a .env file.")

SCOPES    = ["Files.ReadWrite.All", "User.Read"]
AUTH_URL  = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"


def get_redirect_uri(request):
    host = request.get_host()
    scheme = "http" if host.startswith(("localhost", "127.0.0.1")) else "https"
    return f"{scheme}://{host}/auth/redirect"


def home(request):
    return render(request, 'index.html')


@csrf_exempt
def get_access_token(request):
    token = request.session.get("access_token")
    if token:
        return JsonResponse({"access_token": token})
    return JsonResponse({"error": "Not authenticated"}, status=401)


@csrf_exempt
def start_onedrive_auth(request):
    redirect_uri = get_redirect_uri(request)
    params = {
        "client_id":     CLIENT_ID,
        "response_type": "code",
        "redirect_uri":  redirect_uri,
        "scope":         " ".join(SCOPES),
        "response_mode": "query",
    }
    return redirect(f"{AUTH_URL}?{urlencode(params)}")


@csrf_exempt
def onedrive_auth_redirect(request):
    code = request.GET.get("code")
    if not code:
        return JsonResponse({"error": "No code in callback"}, status=400)

    redirect_uri = get_redirect_uri(request)
    data = {
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope":         " ".join(SCOPES),
        "code":          code,
        "redirect_uri":  redirect_uri,
        "grant_type":    "authorization_code",
    }
    resp = requests.post(TOKEN_URL, data=data)
    token_data = resp.json()
    if "access_token" not in token_data:
        return JsonResponse({"error": "Failed to get token", "details": token_data}, status=400)

    request.session['access_token'] = token_data['access_token']
    return render(request, 'auth_success.html', {"token": token_data["access_token"]})



# A single Event that, when set, tells any running stream() to stop ASAP.
cancel_event = threading.Event()



def generate_logs(base_dir, token, action, language, instruction):
    """
    Inline worker: prints to console AND yields each line as SSE.
    """
    # 1) Download
    msg = "Downloading from OneDrive…"
    print(msg, flush=True)
    yield f"data: {msg}\n\n"

    try:
        tmp = tempfile.mkdtemp()
        input_dir, drive_id, _, session_map = download_sharepoint_folder(
            share_link=base_dir,
            temp_dir=tmp,
            access_token=token
        )
    except Exception as e:
        err = f"[ERROR] Download failed: {e}"
        print(err, flush=True)
        yield f"data: {err}\n\n"
        return

    # 2) Find sessions
    sessions = []
    for root, dirs, _ in os.walk(input_dir):
        for d in dirs:
            if d.startswith("Session_"):
                sessions.append(os.path.join(root, d))

    # 3) Process each session
    for sess in sessions:
        if cancel_event.is_set():
            cancel_msg = "[CANCELLED]"
            print(cancel_msg, flush=True)
            yield f"data: {cancel_msg}\n\n"
            return

        name = os.path.basename(sess)
        msg = f"Processing session: {name}"
        print(msg, flush=True)
        yield f"data: {msg}\n\n"

        # run action
        if action == "transcribe":
            runner = Transcriber(sess, language, "cuda" if torch.cuda.is_available() else "cpu")
            runner.process_data(verbose=True)
            uploads = ["transcription.log"]
        elif action == "translate":
            runner = Translator(sess, language, instruction, "cuda" if torch.cuda.is_available() else "cpu")
            runner.process_data(verbose=True)
            uploads = ["translation.log"]
        else:
            gl = Glosser(sess, language, instruction)
            gl.process_data()
            uploads = []

        # always include the annotated spreadsheet
        uploads.append("trials_and_sessions_annotated.xlsx")

        for fn in uploads:
            if cancel_event.is_set():
                cancel_msg = "[CANCELLED]"
                print(cancel_msg, flush=True)
                yield f"data: {cancel_msg}\n\n"
                return

            path = os.path.join(sess, fn)
            if not os.path.exists(path):
                skip = f"Skipping missing file: {fn}"
                print(skip, flush=True)
                yield f"data: {skip}\n\n"
                continue

            up_msg = f"Uploading file: {fn}"
            print(up_msg, flush=True)
            yield f"data: {up_msg}\n\n"

            try:
                upload_file_replace_in_onedrive(
                    local_file_path=path,
                    target_drive_id=drive_id,
                    parent_folder_id=session_map.get(name, ""),
                    file_name_in_folder=fn,
                    access_token=token
                )
            except Exception as e:
                err = f"[ERROR] Upload failed ({fn}): {e}"
                print(err, flush=True)
                yield f"data: {err}\n\n"

        done = f"[DONE UPLOADED] {name}"
        print(done, flush=True)
        yield f"data: {done}\n\n"

    # Final done
    final = "[DONE ALL]"
    print(final, flush=True)
    yield f"data: {final}\n\n"


@csrf_exempt
def stream(request):
    rd = request.GET if request.method == "GET" else request.POST
    base_dir    = rd.get("base_dir")
    action      = rd.get("action")
    language    = rd.get("language")
    instruction = rd.get("instruction")
    token       = rd.get("access_token") or request.session.get("access_token")

    if not base_dir or not token:
        return JsonResponse({"error": "Missing base_dir or access_token"}, status=400)

    # clear any prior cancel
    cancel_event.clear()

    def event_stream():
        yield from generate_logs(base_dir, token, action, language, instruction)

        # if cancellation never happened, we already yielded "[DONE ALL]"
        # no extra frames needed

    resp = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    resp["Cache-Control"]     = "no-cache"
    resp["X-Accel-Buffering"] = "no"
    return resp


@csrf_exempt
def cancel(request):
    """
    Immediately signal any running SSE stream to stop.
    """
    cancel_event.set()
    return JsonResponse({"status": "cancelled"})