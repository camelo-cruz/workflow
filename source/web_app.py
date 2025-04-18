# app.py
import os
import shutil
import tempfile
import threading
import uuid
import logging
import torch
import tqdm
import io
import sys
from queue import Queue, Empty
from contextlib import redirect_stdout, redirect_stderr

from flask import (
    Flask, request, render_template,
    jsonify, Response, stream_with_context
)
from dotenv import load_dotenv

from Transcriber import Transcriber
from Translator import Translator
from Transliterator import Transliterator
from SentenceSelector import SentenceSelector
from Glosser import Glosser

# Load your Hugging/Ffmpeg keys, etc.
load_dotenv("materials/secrets.env", override=True)

device = "cuda" if torch.cuda.is_available() else "cpu"
app = Flask(__name__,
            static_folder="static",
            template_folder="templates")

# job_id -> log Queue
job_queues = {}

def background_work(job_id, tmpdir, action, language, instruction, verbose):
    q: Queue = job_queues[job_id]

    class QueueWriter:
        def write(self, s):
            # only push non‑empty lines
            if s.strip():
                q.put(s)
        def flush(self): pass

    writer = QueueWriter()

    # patch tqdm
    orig_tqdm = tqdm.tqdm
    tqdm.tqdm = lambda *args, **kwargs: orig_tqdm(
        *args, file=writer, leave=True, ascii=True, **{**kwargs}
    )

    # capture stdout/stderr and logging
    with redirect_stdout(writer), redirect_stderr(writer):
        logger = logging.getLogger()
        h = logging.StreamHandler(writer)
        logger.addHandler(h)
        try:
            if action == "Transcribe":
                tr = Transcriber(tmpdir, language, device=device)
                tr.process_data(verbose=verbose)
            elif action == "Translate":
                tx = Translator(tmpdir, language, instruction, device=device)
                tx.process_data(verbose=verbose)
            elif action == "Gloss":
                gl = Glosser(tmpdir, language, instruction, device=device)
                gl.process_data()
            elif action == "Transliterate":
                tl = Transliterator(tmpdir, language, instruction, device=device)
                tl.process_data()
            elif action == "Select sentences":
                ss = SentenceSelector(tmpdir, language, instruction, device=device)
                ss.process_data(verbose=verbose)
            else:
                print(f"Unknown action: {action}", file=sys.stderr)
        except Exception:
            import traceback
            traceback.print_exc(file=writer)
        finally:
            # mark completion, restore, cleanup handler
            q.put(None)
            tqdm.tqdm = orig_tqdm
            logger.removeHandler(h)

@app.route("/process", methods=["POST"])
def process():
    action      = request.form["action"]
    language    = request.form["language"] or None
    instruction = request.form.get("instruction","")
    verbose     = request.form.get("verbose") == "on"

    # Save uploads to a temp folder
    uploaded = request.files.getlist("folder")
    if not uploaded:
        return jsonify(error="No folder uploaded"), 400

    tmpdir = tempfile.mkdtemp(prefix="upload_")
    for f in uploaded:
        dest = os.path.join(tmpdir, f.filename)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        f.save(dest)

    # start the background job
    job_id = str(uuid.uuid4())
    q = Queue()
    job_queues[job_id] = q

    t = threading.Thread(
        target=background_work,
        args=(job_id, tmpdir, action, language, instruction, verbose),
        daemon=True
    )
    t.start()

    return jsonify(job_id=job_id)

@app.route("/logs/<job_id>")
def stream_logs(job_id):
    if job_id not in job_queues:
        return "Unknown job", 404
    q: Queue = job_queues[job_id]

    def event_stream():
        while True:
            try:
                line = q.get(timeout=0.1)
            except Empty:
                continue
            if line is None:
                break
            yield f"data: {line}\n\n"
        # cleanup
        del job_queues[job_id]
        shutil.rmtree(job_queues.get(job_id, ""), ignore_errors=True)

    return Response(stream_with_context(event_stream()),
                    mimetype="text/event-stream")

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)
