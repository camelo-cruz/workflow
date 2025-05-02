import os, sys, threading, tempfile, torch, uuid
from queue      import Queue, Empty
from django.http      import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from .classes.Transcriber                import Transcriber
from .classes.Translator                 import Translator
from .classes.Glosser                    import Glosser
from .utils.onedrive                     import download_sharepoint_folder, upload_file_replace_in_onedrive
from .utils.reorder_columns              import process_columns
from urllib.parse                        import urlencode
import requests

# Try loading secrets from env or .env…
TENANT_ID    = os.getenv("TENANT_ID")
CLIENT_ID    = os.getenv("CLIENT_ID")
CLIENT_SECRET= os.getenv("CLIENT_SECRET")
if not (TENANT_ID and CLIENT_ID and CLIENT_SECRET):
    from pathlib import Path
    from dotenv import load_dotenv
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

jobs = {}  
# jobs[job_id] = {
#   "queue":   Queue(),
#   "logs":    [ ... ],
#   "cancel":  threading.Event(),
#   "finished": False
# }

@csrf_exempt
def get_access_token(request):
    token = request.session.get("access_token")
    return JsonResponse({"access_token": token} if token else {"error": "Not authenticated"}, status=(200 if token else 401))

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
    from django.shortcuts import redirect
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
        return JsonResponse({"error":"Failed to get token","details":data},status=400)
    request.session['access_token'] = data["access_token"]
    from django.shortcuts import render
    return render(request,"auth_success.html",{"token":data["access_token"]})

def _worker(job_id, base_dir, token, action, language, instruction):
    q      = jobs[job_id]["queue"]
    logs   = jobs[job_id]["logs"]
    cancel = jobs[job_id]["cancel"]
    def put(line):
        q.put(line); logs.append(line)

    try:
        put("Downloading from OneDrive…")
        tmp = tempfile.mkdtemp()
        inp, drive_id, _, sess_map = download_sharepoint_folder(
            share_link=base_dir, temp_dir=tmp, access_token=token
        )
        # gather sessions
        sessions = []
        for root, dirs, _ in os.walk(inp):
            for d in dirs:
                if d.startswith("Session_"):
                    sessions.append(os.path.join(root,d))

        for sess in sessions:
            if cancel.is_set():
                put("[CANCELLED]"); break

            name = os.path.basename(sess)
            put(f"Processing session: {name}")
            if action=="transcribe":
                runner = Transcriber(sess, language, "cuda" if torch.cuda.is_available() else "cpu")
                runner.process_data(verbose=True)
                ups = ["transcription.log"]
            elif action=="translate":
                runner = Translator(sess, language, instruction, "cuda" if torch.cuda.is_available() else "cpu")
                runner.process_data(verbose=True)
                ups = ["translation.log"]
            elif action=="gloss":
                g = Glosser(sess, language, instruction)
                g.process_data()
                ups = []
            elif action=="create columns":
                process_columns(sess, language)
                ups = []

            ups.append("trials_and_sessions_annotated.xlsx")
            for fn in ups:
                if cancel.is_set():
                    put("[CANCELLED]"); break
                path = os.path.join(sess,fn)
                if not os.path.exists(path):
                    put(f"Skipping missing file: {fn}"); continue
                put(f"Uploading file: {fn}")
                upload_file_replace_in_onedrive(
                    local_file_path=path,
                    target_drive_id=drive_id,
                    parent_folder_id=sess_map.get(name,""),
                    file_name_in_folder=fn,
                    access_token=token
                )
            put(f"[DONE UPLOADED] {name}")

        if not cancel.is_set():
            put("[DONE ALL]")

    except Exception as e:
        put(f"[ERROR] {e}")
    finally:
        jobs[job_id]["finished"] = True

@csrf_exempt
def process(request):
    if request.method!="POST":
        return JsonResponse({"error":"Use POST"},status=400)
    base_dir    = request.POST.get("base_dir")
    token       = request.session.get("access_token") or request.POST.get("access_token")
    action      = request.POST.get("action")
    language    = request.POST.get("language")
    instruction = request.POST.get("instruction")
    if not (base_dir and token):
        return JsonResponse({"error":"Missing params"},status=400)

    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "queue":   Queue(),
        "logs":    [],
        "cancel":  threading.Event(),
        "finished": False
    }
    th = threading.Thread(
        target=_worker,
        args=(job_id, base_dir, token, action, language, instruction),
        daemon=True
    )
    jobs[job_id]["thread"] = th
    th.start()
    return JsonResponse({"job_id":job_id})

@csrf_exempt
def stream(request, job_id):
    if job_id not in jobs:
        return JsonResponse({"error":"Unknown job_id"},status=404)
    job = jobs[job_id]
    def event_stream():
        for line in job["logs"]:
            yield f"data: {line}\n\n"
        q = job["queue"]
        while not (job["finished"] and q.empty()):
            try:
                line = q.get(timeout=1)
                yield f"data: {line}\n\n"
            except Empty:
                continue

    resp = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    resp["Cache-Control"]     = "no-cache"
    resp["X-Accel-Buffering"] = "no"
    return resp

@csrf_exempt
def cancel(request):
    import json
    body = json.loads(request.body.decode())
    jid  = body.get("job_id")
    job  = jobs.get(jid)
    if not job:
        return JsonResponse({"error":"Unknown job_id"},status=404)
    job["cancel"].set()
    return JsonResponse({"status":"cancelled"})
