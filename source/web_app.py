from contextlib import redirect_stderr, redirect_stdout
import os, shutil, tempfile, threading, uuid, logging, torch
import tqdm
import io, sys
from flask import (
    Flask, request, render_template,
    jsonify, Response, stream_with_context
)
from dotenv import load_dotenv
from queue import Queue, Empty

from Transcriber import Transcriber
# … other imports …

load_dotenv("materials/secrets.env", override=True)
device = "cuda" if torch.cuda.is_available() else "cpu"
app = Flask(__name__,
            static_folder="static",
            template_folder="templates")

# In‑memory map of job_id → log‑Queue
job_queues = {}

def background_work(job_id, tmpdir, action, language, instruction, verbose):
    q: Queue = job_queues[job_id]
    # writer that puts each write() call into the queue
    class QueueWriter:
        def write(self, s):
            if s.strip():
                q.put(s)
        def flush(self): pass

    writer = QueueWriter()

    # Monkey‑patch tqdm to write into our writer
    orig_tqdm = tqdm.tqdm
    tqdm.tqdm = lambda *args, **kwargs: orig_tqdm(
        *args, file=writer, **{**kwargs, "leave": True}
    )

    # Also patch stdout / stderr
    with redirect_stdout(writer), redirect_stderr(writer):
        logger = logging.getLogger()
        h = logging.StreamHandler(writer)
        logger.addHandler(h)
        try:
            if action == "Transcribe":
                tr = Transcriber(tmpdir, language, device=device)
                tr.process_data(verbose=verbose)
            # … other actions …
            else:
                print(f"Unknown action: {action}", file=sys.stderr)
        except Exception:
            import traceback
            traceback.print_exc(file=writer)
        finally:
            # signal completion
            q.put(None)
            # restore
            tqdm.tqdm = orig_tqdm
            logger.removeHandler(h)

@app.route("/process", methods=["POST"])
def process():
    action      = request.form["action"]
    language    = request.form["language"]
    instruction = request.form.get("instruction","")
    verbose     = request.form.get("verbose")=="on"

    # save upload to tmpdir…
    uploaded = request.files.getlist("folder")
    tmpdir = tempfile.mkdtemp(prefix="upload_")
    for f in uploaded:
        dest = os.path.join(tmpdir, f.filename)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        f.save(dest)

    # create job
    job_id = str(uuid.uuid4())
    q = Queue()
    job_queues[job_id] = q

    # start background thread
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
            # SSE protocol: “data: …\n\n”
            yield f"data: {line}\n\n"
        # cleanup
        del job_queues[job_id]
        # remove tmpdir: you could store tmpdir per job if needed

    return Response(stream_with_context(event_stream()),
                    mimetype="text/event-stream")

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)
