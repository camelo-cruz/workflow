import os
import shutil
import uuid
import threading
import io
import torch
from queue import Queue, Empty
from contextlib import redirect_stdout, redirect_stderr

from flask import (
    Flask, request, render_template,
    jsonify, Response, stream_with_context, send_file
)
from dotenv import load_dotenv

from Transcriber import Transcriber  # your existing logic

load_dotenv("materials/secrets.env", override=True)

device = "cuda" if torch.cuda.is_available() else "cpu"
app = Flask(__name__,
            static_folder="static",
            template_folder="templates")

UPLOAD_ROOT = os.path.abspath("uploads")
os.makedirs(UPLOAD_ROOT, exist_ok=True)

# job_id -> { queue: Queue(), finished: bool }
jobs = {}

def run_transcription(job_id, session_path, language, verbose):
    q = jobs[job_id]["queue"]

    class QueueWriter(io.TextIOBase):
        def write(self, text):
            # split on newlines and push each line
            for line in text.rstrip().splitlines():
                q.put(line)
        def flush(self): pass

    qw = QueueWriter()
    try:
        with redirect_stdout(qw), redirect_stderr(qw):
            print(f"[INFO] language given {language}")
            transcriber = Transcriber(
                input_dir=session_path,
                language=language,
                device=device,
            )
            transcriber.process_data(verbose=verbose)
        q.put("[DONE]")
    except Exception as e:
        q.put(f"[ERROR] {e}")
    finally:
        jobs[job_id]["finished"] = True

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/process", methods=["POST"])
def process():
    # 1) pull form fields
    action      = request.form.get("action")
    language    = request.form.get("language", "").strip()
    print(f"[INFO] language gotten: {language}")
    instruction = request.form.get("instruction", "")
    verbose     = request.form.get("verbose") == "on"

    # 2) get all uploaded files from the 'folder' <input>
    files = request.files.getlist("folder")
    if not files:
        return jsonify({"error": "No folder uploaded."}), 400

    # 3) make a unique work directory
    job_id = str(uuid.uuid4())
    session_path = os.path.join(UPLOAD_ROOT, job_id)
    os.makedirs(session_path, exist_ok=True)

    # 4) reconstruct the folder tree
    for f in files:
        # f.filename holds the relative path e.g. "session42/binaries/audio.mp3"
        dest = os.path.join(session_path, f.filename)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        f.save(dest)

    # 5) enqueue and spawn the background thread
    q = Queue()
    jobs[job_id] = {"queue": q, "finished": False}
    thread = threading.Thread(
        target=run_transcription,
        args=(job_id, session_path, language, verbose),
        daemon=True
    )
    thread.start()

    # 6) immediately return the job ID
    return jsonify({"job_id": job_id})

@app.route("/logs/<job_id>")
def logs(job_id):
    if job_id not in jobs:
        return jsonify({"error": "Unknown job ID"}), 404

    def event_stream():
        q = jobs[job_id]["queue"]
        while True:
            try:
                line = q.get(timeout=0.5)
                yield f"data: {line}\n\n"
                if line == "[DONE]" or line.startswith("[ERROR]"):
                    break
            except Empty:
                if jobs[job_id]["finished"]:
                    break

        # tell client we’re done
        yield "event: close\ndata: \n\n"

    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream"
    )

@app.route("/download/<job_id>")
def download(job_id):
    session_root = os.path.join(UPLOAD_ROOT, job_id)

    # 1) look for any *_annotated.xlsx under the job directory
    annotated = []
    for dirpath, _, files in os.walk(session_root):
        for f in files:
            if f.endswith("_annotated.xlsx"):
                annotated.append(os.path.join(dirpath, f))

    if not annotated:
        return jsonify({"error": "Output file not found."}), 404

    # 2) if only one, send it directly
    if len(annotated) == 1:
        return send_file(
            annotated[0],
            as_attachment=True,
            download_name=os.path.basename(annotated[0])
        )

    # 3) otherwise bundle everything into a ZIP
    zip_path = shutil.make_archive(session_root, "zip", session_root)
    return send_file(
        zip_path,
        mimetype="application/zip",
        as_attachment=True,
        download_name=os.path.basename(zip_path)
    )

if __name__ == "__main__":
    app.run(debug=True)
