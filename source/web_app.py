# app.py
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

load_dotenv("materials/secrets.env", override=True)
device = "cuda" if torch.cuda.is_available() else "cpu"

app = Flask(__name__,
            static_folder="static",
            template_folder="templates")

UPLOAD_ROOT = os.path.abspath("uploads")
os.makedirs(UPLOAD_ROOT, exist_ok=True)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/process", methods=["POST"])
def process():
    # pick up the folder input
    files = request.files.getlist("folder")
    language = request.form.get("language", "").strip() or "en"
    verbose  = request.form.get("verbose") == "on"

    if not files:
        return jsonify({"error": "No folder uploaded."}), 400

    # create a unique job folder and reconstruct the session tree under it
    job_id = str(uuid.uuid4())
    session_path = os.path.join(UPLOAD_ROOT, job_id)
    for f in files:
        dest = os.path.join(session_path, f.filename)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        f.save(dest)

    # **synchronous** processing**:
    transcriber = Transcriber(
        input_dir=session_path,
        language=language,
        device=device,
    )
    transcriber.process_data(verbose=verbose)

    # find the output(s)
    annotated = []
    for dp, _, fnames in os.walk(session_path):
        for fname in fnames:
            if fname.endswith("_annotated.xlsx"):
                annotated.append(os.path.join(dp, fname))

    if not annotated:
        return jsonify({"error": "No output file generated."}), 500

    # if just one, send it; otherwise bundle into a zip
    if len(annotated) == 1:
        path = annotated[0]
        return send_file(
            path,
            as_attachment=True,
            download_name=os.path.basename(path)
        )
    else:
        zip_path = shutil.make_archive(session_path, "zip", session_path)
        return send_file(
            zip_path,
            mimetype="application/zip",
            as_attachment=True,
            download_name=os.path.basename(zip_path)
        )

if __name__ == "__main__":
    app.run(debug=True)
