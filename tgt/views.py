import uuid
import torch
import threading
import io
import tempfile
import os
from queue import Queue, Empty
from contextlib import redirect_stdout, redirect_stderr
from django.http import JsonResponse, StreamingHttpResponse, HttpResponse
from django.shortcuts import render
from .classes.Transcriber import Transcriber
from .classes.Translator import Translator
from .classes.Glosser import Glosser
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.middleware.csrf import get_token

from .utils.onedrive import download_sharepoint_folder, upload_file_replace_in_onedrive

# Simple in-memory job store
jobs = {}  # job_id -> {"queue": Queue(), "finished": bool, "cancelled": bool}

@ensure_csrf_cookie
def index(request):
    token = get_token(request)
    print(f"CSRF token on render: {token}")
    return render(request, 'index.html')


def process(request):
    if request.method == 'POST':
        onedrive_link = request.POST.get('base_dir')
        language = request.POST.get('language')
        action = request.POST.get('action')
        instruction = request.POST.get('instruction')

        if not onedrive_link:
            return JsonResponse({'error': 'Missing base_dir or OneDrive link'}, status=400)

        job_id = str(uuid.uuid4())
        q = Queue()
        jobs[job_id] = {"queue": q, "finished": False, "cancelled": False}

        def log_worker():
            class QueueWriter(io.TextIOBase):
                def write(self, txt):
                    for line in txt.rstrip().splitlines():
                        q.put(line)
                def flush(self): pass

            writer = QueueWriter()

            try:
               with redirect_stdout(writer), redirect_stderr(writer):
                    temp_dir = tempfile.mkdtemp()

                    input_dir, drive_id, parent_id, session_folder_id_map = download_sharepoint_folder(onedrive_link, temp_dir)

                    # Determine real session folders
                    session_folders = []

                    first_level_entries = os.listdir(input_dir)

                    if all(entry.startswith("Session_") for entry in first_level_entries):
                        # Sessions are directly inside input_dir
                        for session_folder_name in first_level_entries:
                            session_folder_path = os.path.join(input_dir, session_folder_name)
                            if os.path.isdir(session_folder_path):
                                session_folders.append(session_folder_path)
                    else:
                        # Sessions are nested inside collections (like test_alejandra/)
                        for collection_folder in first_level_entries:
                            collection_path = os.path.join(input_dir, collection_folder)
                            if not os.path.isdir(collection_path):
                                continue
                            for session_folder_name in os.listdir(collection_path):
                                session_folder_path = os.path.join(collection_path, session_folder_name)
                                if os.path.isdir(session_folder_path) and session_folder_name.startswith("Session_"):
                                    session_folders.append(session_folder_path)


                    # 3. Now process all session folders
                    for session_folder_path in session_folders:
                        if jobs[job_id].get("cancelled"):
                            q.put("[CANCELLED]")
                            break

                        session_folder_name = os.path.basename(session_folder_path)
                        print(f"Processing session: {session_folder_name}")

                        files_to_upload = ["trials_and_sessions_annotated.xlsx"]

                        if action == 'transcribe':
                            transcriber = Transcriber(
                                input_dir=session_folder_path,
                                language=language,
                                device='cuda' if torch.cuda.is_available() else 'cpu'
                            )
                            transcriber.process_data(verbose=True)
                            files_to_upload.append("transcription.log")
                        elif action == 'translate':
                            translator = Translator(
                                input_dir=session_folder_path,
                                language=language,
                                instruction=instruction,
                                device='cuda' if torch.cuda.is_available() else 'cpu'
                            )
                            translator.process_data(verbose=True)
                            files_to_upload.append("translation.log")
                        elif action == 'gloss':
                            glosser = Glosser(
                                input_dir=session_folder_path,
                                language=language,
                                instruction=instruction,
                            )
                            glosser.process_data()

                        # 4. Upload processed files
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
                                    file_name_in_folder=file_name
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


        threading.Thread(target=log_worker, daemon=True).start()
        return JsonResponse({'job_id': job_id})

    return JsonResponse({'error': 'Invalid request method'}, status=400)

def logs(request, job_id):
    if job_id not in jobs:
        return HttpResponse("Unknown job ID", status=404)

    def event_stream():
        q = jobs[job_id]['queue']
        while True:
            try:
                line = q.get(timeout=0.5)
            except Empty:
                if jobs[job_id]['finished']:
                    break
                continue
            yield f"data: {line}\n\n"
            if line in ("[DONE ALL]", "[CANCELLED]") or line.startswith("[ERROR]"):
                break

    return StreamingHttpResponse(event_stream(), content_type='text/event-stream')

def cancel(request, job_id):
    if request.method == 'POST':
        if job_id in jobs:
            jobs[job_id]["cancelled"] = True
            return JsonResponse({"status": "cancelling"})
        else:
            return JsonResponse({"error": "Unknown job ID"}, status=404)

    return JsonResponse({'error': 'Invalid request method'}, status=400)
