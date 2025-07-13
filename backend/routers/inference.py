import os
import uuid
import multiprocessing
import shutil
import queue
import asyncio
from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from zipfile import ZipFile
from pathlib import Path
import tempfile

from fastapi import APIRouter, Request, Form, UploadFile, File, Body, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse

from .inference_workers import _offline_worker, _online_worker

router = APIRouter()

MODELS_BASE = Path(__file__).parent.parent / "models"

jobs: dict[str, dict] = {}

@router.post("/process")
async def process(
    request: Request,
    action: str = Form(...),
    language: str = Form(...),
    glossingModel: str | None = Form(None),
    translationModel: str | None = Form(None),
    instruction: str | None = Form(None),
    access_token: str | None = Form(None),
    zipfile: UploadFile | None = File(None),
    base_dir: str | None = Form(None),
):
    job_id = str(uuid.uuid4())
    q = multiprocessing.Queue()
    cancel = multiprocessing.Event()
    token = access_token  # “token” now comes from form data
    jobs[job_id] = {
        "queue": q,
        "cancel": cancel,
        "zip_path": None,
        "token": token,
    }
    if glossingModel == "Default":
        glossingModel = None
    if translationModel == "Default":
        translationModel = None

    if not language:
        q.put("[ERROR] Missing language")
        return {"job_id": job_id}

    if zipfile is not None:
        tmp_dir = tempfile.mkdtemp()
        zip_path = Path(tmp_dir) / "upload.zip"
        contents = await zipfile.read()
        with open(zip_path, "wb") as f:
            f.write(contents)
        with ZipFile(zip_path, "r") as archive:
            archive.extractall(tmp_dir)
        os.remove(zip_path)

        worker = _offline_worker
        args = (job_id, tmp_dir, action, language, instruction, q, cancel)
        jobs[job_id]["base_dir"] = tmp_dir

    else:
        if not (base_dir and token):
            raise HTTPException(status_code=400, detail="Missing base_dir or token")
        worker = _online_worker
        args = (job_id, base_dir, token, action, language, instruction, translationModel, glossingModel, q, cancel)

    p = multiprocessing.Process(target=worker, args=args, daemon=True)
    p.start()
    jobs[job_id]["process"] = p

    return {"job_id": job_id}


@router.get("/{job_id}/download")
async def download_zip(job_id: str, background_tasks: BackgroundTasks):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="No job")
    zip_path = job.get("zip_path")
    if not zip_path:
        raise HTTPException(status_code=404, detail="No zip path")

    base_dir = job.get("base_dir")

    def cleanup():
        try:
            os.remove(zip_path)
        except OSError:
            pass
        if base_dir and os.path.isdir(base_dir):
            shutil.rmtree(base_dir, ignore_errors=True)
        jobs.pop(job_id, None)

    background_tasks.add_task(cleanup)

    return FileResponse(
        path=zip_path,
        media_type="application/zip",
        filename=f"{job_id}_results.zip"
    )

def get_job_or_404(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown job_id")
    return job

@router.get("/{job_id}/stream")
async def stream(job_id: str):
    """
    Stream server-sent events from a multiprocessing.Queue using EventSourceResponse.
    Guarantees proper end-of-stream framing.
    """
    job = get_job_or_404(job_id)
    q: multiprocessing.Queue = job["queue"]

    async def event_publisher():
        # Continuously pull from the blocking multiprocessing.Queue in a threadpool
        loop = asyncio.get_event_loop()
        while True:
            # Offload blocking q.get() to thread pool
            line = await loop.run_in_executor(None, q.get)

            # Handle ZIP path messages internally
            if isinstance(line, str) and line.startswith("[ZIP PATH] "):
                zip_path = line[len("[ZIP PATH] "):].strip()
                job["zip_path"] = zip_path
                continue

            # Yield SSE data event
            yield {"data": line}

            # Break on termination
            if line == "[DONE ALL]":
                break

    return EventSourceResponse(event_publisher())

@router.post("/cancel")
async def cancel_job(payload: dict = Body(...)):
    jid = payload.get("job_id")
    job = jobs.get(jid)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown job_id")

    q: multiprocessing.Queue = job["queue"]
    q.put("[CANCELLED]")
    q.put("[DONE ALL]")

    proc = job.get("process")
    if proc and proc.is_alive():
        proc.terminate()

    jobs.pop(jid, None)
    return {"status": "cancelled"}


@router.get("/models/{task}")
async def list_models(task: str):
    if task not in ["translation", "glossing"]:
        return JSONResponse({"error": "Invalid task"}, status_code=400)
    
    model_dir = MODELS_BASE / task
    print(f"Models base directory: {MODELS_BASE}")
    if not model_dir.exists() or not model_dir.is_dir():
        print(f"No models found for task '{task}'")
        return JSONResponse({"models": []})
    
    model_names = [d.name for d in model_dir.iterdir() if d.is_dir()]
    print(f"Found models: {model_names}")
    return {"models": model_names}