import os
import uuid
import shutil
import torch
from flask import (
    Flask, request, render_template,
    send_file, jsonify
)
from dotenv import load_dotenv

from Transcriber import Transcriber
from Translator import Translator
import threading, io
from queue import Queue, Empty
from contextlib import redirect_stdout, redirect_stderr
from flask import Response, stream_with_context

load_dotenv("materials/secrets.env", override=True)
device = "cuda" if torch.cuda.is_available() else "cpu"

app = Flask(__name__,
            static_folder="static",
            template_folder="templates")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/list_dirs", methods=["GET"])
def list_dirs():
    base = request.args.get("base", "").strip().strip("'").strip('"')
    # sanity check
    if not base or not os.path.isdir(base):
        return jsonify({"error": "Invalid base directory"}), 400

    subs = sorted(d for d in os.listdir(base)
                  if os.path.isdir(os.path.join(base, d)))
    return jsonify(subs)

jobs = {}  # job_id -> {"queue": Queue(), "finished": bool}

def run_transcription(job_id, base_dir, language, verbose):
    q = jobs[job_id]["queue"]

    class QueueWriter(io.TextIOBase):
        def write(self, txt):
            for line in txt.rstrip().splitlines():
                q.put(line)
        def flush(self): pass

    qw = QueueWriter()
    try:
        with redirect_stdout(qw), redirect_stderr(qw):
            t = Transcriber(
                input_dir=base_dir,
                language=language,
                device=device
            )
            t.process_data(verbose=verbose)
        q.put("[DONE]")
    except Exception as e:
        q.put(f"[ERROR] {e}")
    finally:
        jobs[job_id]["finished"] = True

def run_translation(job_id, base_dir, language, verbose):
    q = jobs[job_id]["queue"]

    class QueueWriter(io.TextIOBase):
        def write(self, txt):
            for line in txt.rstrip().splitlines():
                q.put(line)
        def flush(self): pass

    qw = QueueWriter()
    try:
        with redirect_stdout(qw), redirect_stderr(qw):
            t = Translator(
                input_dir=base_dir,
                language=language,
                device=device
            )
            t.process_data(verbose=verbose)
        q.put("[DONE]")
    except Exception as e:
        q.put(f"[ERROR] {e}")
    finally:
        jobs[job_id]["finished"] = True

@app.route("/process", methods=["POST"])
def process():
    action = request.form.get("action", "").strip()
    base_dir = request.form.get("base_dir","").strip()
    language = request.form.get("language","").strip()
    instruction = request.form.get("instruction","").strip()
    if not base_dir or not os.path.isdir(base_dir):
        return jsonify({"error":"Invalid base directory"}),400

    # start a background job
    job_id = str(uuid.uuid4())
    q = Queue()
    jobs[job_id] = {"queue": q, "finished": False}
    if action == 'transcribe':
        thread = threading.Thread(
            target=run_transcription,
            args=(job_id, base_dir, language, True),
            daemon=True
        )
        thread.start()
    elif action == 'translate':
        thread = threading.Thread(
            target=run_translation,
            args=(job_id, base_dir, language, True),
            daemon=True
        )
        thread.start()

    return jsonify({"job_id": job_id})

@app.route("/logs/<job_id>")
def logs(job_id):
    if job_id not in jobs:
        return "Unknown job ID", 404

    def event_stream():
        q = jobs[job_id]["queue"]
        while True:
            try:
                line = q.get(timeout=0.5)
            except Empty:
                if jobs[job_id]["finished"]:
                    break
                continue
            yield f"data: {line}\n\n"
            if line in ("[DONE]",) or line.startswith("[ERROR]"):
                break

    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream"
    )

if __name__ == "__main__":
    app.run(debug=True)
