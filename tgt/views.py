import io
import os
import tempfile
import torch
from contextlib import redirect_stdout, redirect_stderr
from urllib.parse import urlencode

import requests
from django.http import JsonResponse, StreamingHttpResponse, HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt

from .classes.Transcriber import Transcriber
from .classes.Translator import Translator
from .classes.Glosser import Glosser
from .utils.onedrive import download_sharepoint_folder, upload_file_replace_in_onedrive

TENANT_ID     = '7ef3035c-bf11-463a-ab3b-9a9a4ac82500'
CLIENT_ID     = '58c0d230-141d-4a30-905e-fd63e331e5ea'
CLIENT_SECRET = 'sY38Q~CknTafzzQQ37TS9QTKD256Z3aovopynbWZ'

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


def generate_logs(onedrive_link, access_token, action, language, instruction):
    """
    Download from OneDrive, run transcribe/translate/gloss,
    upload results, and yield each log‐line as SSE frames.
    """
    class StreamWriter(io.TextIOBase):
        def write(self, txt):
            # split lines and yield SSE‐formatted chunks
            for line in txt.rstrip().splitlines():
                yield f"data: {line}\n\n"
        def flush(self): pass

    writer = StreamWriter()
    try:
        with redirect_stdout(writer), redirect_stderr(writer):
            temp_dir = tempfile.mkdtemp()
            input_dir, drive_id, _, session_map = download_sharepoint_folder(
                share_link=onedrive_link,
                temp_dir=temp_dir,
                access_token=access_token
            )

            # find all “Session_*” subfolders
            sessions = []
            for root, dirs, _ in os.walk(input_dir):
                for d in dirs:
                    if d.startswith("Session_"):
                        sessions.append(os.path.join(root, d))

            for session_path in sessions:
                # log processing start
                yield from writer.write(f"Processing session: {os.path.basename(session_path)}")

                # run the requested action
                if action == "transcribe":
                    proc = Transcriber(
                        session_path,
                        language,
                        "cuda" if torch.cuda.is_available() else "cpu"
                    )
                    proc.process_data(verbose=True)
                    uploads = ["transcription.log"]
                elif action == "translate":
                    proc = Translator(
                        session_path, language, instruction,
                        "cuda" if torch.cuda.is_available() else "cpu"
                    )
                    proc.process_data(verbose=True)
                    uploads = ["translation.log"]
                else:  # gloss
                    g = Glosser(session_path, language, instruction)
                    g.process_data()
                    uploads = []

                # always include the annotated spreadsheet
                uploads.append("trials_and_sessions_annotated.xlsx")

                # upload any generated files
                for fn in uploads:
                    local = os.path.join(session_path, fn)
                    if not os.path.exists(local):
                        yield from writer.write(f"Skipping missing file: {fn}")
                        continue

                    yield from writer.write(f"Uploading file: {fn}")
                    folder_id = session_map.get(os.path.basename(session_path))
                    if folder_id:
                        upload_file_replace_in_onedrive(
                            local_file_path=local,
                            target_drive_id=drive_id,
                            parent_folder_id=folder_id,
                            file_name_in_folder=fn,
                            access_token=access_token
                        )
                    else:
                        yield from writer.write(f"⚠️ No OneDrive folder ID for session, skipping upload")

                yield from writer.write(f"[DONE UPLOADED] {os.path.basename(session_path)}")

            # all sessions done
            yield "data: [DONE ALL]\n\n"

    except Exception as e:
        yield f"data: [ERROR] {e}\n\n"


@csrf_exempt
def stream(request):
    """
    SSE endpoint that both kicks off and streams your workflow.
    Frontend can open:
       new EventSource(`/stream/?${params}`)
    where params include base_dir, action, language, instruction, access_token.
    """
    # gather params from GET or POST
    rd = request.GET if request.method == "GET" else request.POST
    onedrive_link = rd.get("base_dir")
    action        = rd.get("action")
    language      = rd.get("language")
    instruction   = rd.get("instruction")
    access_token  = (
        request.session.get("access_token")
        or rd.get("access_token")
    )

    if not onedrive_link or not access_token:
        return JsonResponse({"error": "Missing base_dir or access_token"}, status=400)

    def event_stream():
        try:
            yield from generate_logs(onedrive_link, access_token, action, language, instruction)
            yield "data: [DONE ALL]\n\n"
        except Exception as e:
            yield f"data: [ERROR] {e}\n\n"

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"]     = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response