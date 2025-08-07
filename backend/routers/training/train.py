import os
import uuid
import shutil
import tempfile
import asyncio
import logging
from pathlib import Path
from zipfile import ZipFile
from fastapi import APIRouter, HTTPException, Request, Form, UploadFile, File, Body, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from sse_starlette.sse import EventSourceResponse
from multiprocessing import Process, Queue, Event
from routers.training.train_workers import OneDriveWorker
from routers.helpers.job_manager import JobManager

logger = logging.getLogger(__name__)
router = APIRouter()

MODELS_BASE = Path(__file__).resolve().parent.parent / "models"

async def run_worker(process_fn):
    proc = Process(target=process_fn, daemon=True)
    proc.start()
    return proc


@router.post("/process")
async def process(
    request: Request,
    base_dir: str | None = Form(None),
    study: str | None = Form(None),
    action: str = Form(...),
    language: str = Form(...),
    access_token: str | None = Form(None),
    zipfile: UploadFile | None = File(None),
):
    job = JobManager.create()
    job.token = access_token

    if not language:
        job.queue.put("[ERROR] Missing language")
        return {"job_id": job.id}

    if zipfile:
        tmp_dir = tempfile.mkdtemp()
        archive_path = Path(tmp_dir) / "upload.zip"
        contents = await zipfile.read()
        archive_path.write_bytes(contents)
        with ZipFile(archive_path, 'r') as archive:
            archive.extractall(tmp_dir)
        archive_path.unlink()

        #TODO: Handle the case where multiple files are uploaded
    else:
        if not base_dir or not access_token:
            raise HTTPException(status_code=400, detail="Missing base_dir or access_token for online processing")
        worker_fn = OneDriveWorker(base_dir, language, action, study, access_token, job)

    job.process = await run_worker(worker_fn.run)
    return {"job_id": job.id}


@router.get("/{job_id}/stream")
async def stream(job_id: str):
    job = JobManager.get(job_id)

    async def event_generator():
        loop = asyncio.get_event_loop()
        while True:
            message = await loop.run_in_executor(None, job.queue.get)
            if isinstance(message, str) and message.startswith("[ZIP PATH] "):
                job.zip_path = message.replace("[ZIP PATH] ", "").strip()
                continue
            yield {"data": message}
            if message == "[DONE ALL]":
                break

    return EventSourceResponse(event_generator())

@router.post("/cancel")
async def cancel(payload: dict = Body(...)):
    job_id = payload.get("job_id")
    job = JobManager.get(job_id)
    job.queue.put("[CANCELLED]")
    job.queue.put("[DONE ALL]")
    if job.process and job.process.is_alive():
        job.process.terminate()
    JobManager.remove(job_id)
    return {"status": "cancelled"}
