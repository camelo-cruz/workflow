# server.py
from flask import Flask, request, jsonify
from Transcriber import Transcriber
import torch

app = Flask(__name__)
device = 'cuda' if torch.cuda.is_available() else 'cpu'

API_KEY = 'xxx'

@app.before_request
def check_api_key():
    auth = request.headers.get("Authorization")
    if auth != f"Bearer {API_KEY}":
        return jsonify({"error": "Unauthorized"}), 401

@app.route("/transcribe", methods=["POST"])
def transcribe():
    data = request.json
    input_dir = data.get("input_dir")
    language = data.get("language")
    verbose = data.get("verbose", False)

    try:
        transcriber = Transcriber(input_dir, language, device=device)
        transcriber.process_data(verbose=verbose)
        return jsonify({"message": "✅ Transcription complete"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
