import os
import shutil
import tempfile
import torch
from flask import Flask, request, render_template, jsonify
from dotenv import load_dotenv

from Transcriber import Transcriber
from Translator import Translator
from Transliterator import Transliterator
from SentenceSelector import SentenceSelector
from Glosser import Glosser

# Load .env
load_dotenv("materials/secrets.env", override=True)

device = "cuda" if torch.cuda.is_available() else "cpu"
app = Flask(
    __name__,
    static_folder="static",
    template_folder="templates"
)

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/process", methods=["POST"])
def process():
    action      = request.form["action"]
    language    = request.form["language"]
    instruction = request.form.get("instruction", "")
    verbose     = request.form.get("verbose") == "on"

    # Collect all uploaded files from the 'folder' input
    uploaded_files = request.files.getlist("folder")
    tmpdir = tempfile.mkdtemp(prefix="upload_")
    if not uploaded_files:
        return jsonify(error="No folder uploaded"), 400

    try:
        # Save each file under its relative path
        for f in uploaded_files:
            # f.filename might include subdirs if you used webkitdirectory
            dest_path = os.path.join(tmpdir, f.filename)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            f.save(dest_path)

        # Now call your processing
        if action == "Transcribe":
            tr = Transcriber(tmpdir, language, device=device)
            tr.process_data(verbose=verbose)
            return jsonify(result="Transcription completed")

        elif action == "Translate":
            tx = Translator(tmpdir, language, instruction, device=device)
            tx.process_data(verbose=verbose)
            return jsonify(result="Translation completed")

        elif action == "Gloss":
            gl = Glosser(tmpdir, language, instruction, device=device)
            gl.process_data()
            return jsonify(result="Glossing completed")

        elif action == "Transliterate":
            #tl = Transliterator(tmpdir, language, instruction, device=device)
            #tl.process_data()
            #return jsonify(result="Transliteration completed")
            return jsonify(result="Sentence selection not implemented yet")

        elif action == "Select sentences":
            #ss = SentenceSelector(tmpdir, language, instruction, device=device)
            #ss.process_data(verbose=verbose)
            #return jsonify(result="Sentence selection completed")
            return jsonify(result="Sentence selection not implemented yet")
        
        else:
            return jsonify(error=f"Unknown action: {action}"), 400

    except Exception as e:
        return jsonify(error=str(e)), 500

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

if __name__ == "__main__":
    app.run(debug=True)
