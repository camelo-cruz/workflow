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
from routers.helpers.train_workers import OneDriveWorker

logger = logging.getLogger(__name__)
router = APIRouter()

MODELS_BASE = Path(__file__).resolve().parent.parent / "models"

class Job:
    def __init__(self, job_id: str):
        self.id = job_id
        self.queue: Queue = Queue()
        self.cancel_event: Event = Event()
        self.base_dir: str | None = None
        self.zip_path: str | None = None
        self.token: str | None = None
        self.process: Process | None = None

class JobManager:
    _jobs: dict[str, Job] = {}

    @classmethod
    def create(cls) -> Job:
        job_id = str(uuid.uuid4())
        job = Job(job_id)
        cls._jobs[job_id] = job
        return job

    @classmethod
    def get(cls, job_id: str) -> Job:
        job = cls._jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
        return job

    @classmethod
    def remove(cls, job_id: str):
        cls._jobs.pop(job_id, None)


async def run_worker(process_fn):
    proc = Process(target=process_fn, daemon=True)
    proc.start()
    return proc


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
    study: str | None = Form(None),
):
    # Initialize job
    job = JobManager.create()
    job.token = access_token

    # Normalize model names
    glossingModel = None if glossingModel == "Default" else glossingModel
    translationModel = None if translationModel == "Default" else translationModel

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

        worker_fn = ZipWorker(tmp_dir, action, 
                              language, instruction, 
                              translationModel, glossingModel, 
                              job)
        job.base_dir = tmp_dir
    else:
        if not base_dir or not access_token:
            raise HTTPException(status_code=400, detail="Missing base_dir or access_token for online processing")
        worker_fn = OneDriveWorker(base_dir, action, 
                                   language, instruction, 
                                   translationModel, glossingModel, study, access_token, job)

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


@router.get("/{job_id}/download")
async def download(job_id: str, background_tasks: BackgroundTasks):
    job = JobManager.get(job_id)
    if not job.zip_path:
        raise HTTPException(status_code=404, detail="Results not ready")

    def cleanup():
        try:
            os.remove(job.zip_path)
        except OSError:
            logger.warning(f"Failed to delete zip file {job.zip_path}")
        if job.base_dir and os.path.isdir(job.base_dir):
            shutil.rmtree(job.base_dir, ignore_errors=True)
        JobManager.remove(job_id)

    background_tasks.add_task(cleanup)
    return FileResponse(
        path=job.zip_path,
        media_type="application/zip",
        filename=f"{job.id}_results.zip"
    )

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


@router.get("/models/{task}")
async def list_models(task: str):
    if task not in ("translation", "glossing"):
        raise HTTPException(status_code=400, detail="Invalid task")

    dir_path = MODELS_BASE / task
    if not dir_path.is_dir():
        return {"models": []}

    models = [d.name for d in dir_path.iterdir() if d.is_dir()]
    return {"models": models}
