import os
import shutil
import tempfile
import asyncio
import logging
from pathlib import Path
from zipfile import ZipFile
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Form, UploadFile, File, Body, BackgroundTasks
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse

from routers.helpers.job_manager import JobManager, ProcessingService, JobCleanupService

logger = logging.getLogger(__name__)
router = APIRouter()

MODELS_BASE = Path(__file__).resolve().parent.parent.parent / "models"
VALID_TASKS = {"transcribe", "translate", "transliterate", "gloss"}


@router.post("/process")
async def process(
    request: Request,
    action: str = Form(...),
    language: str = Form(...),
    glossingModel: Optional[str] = Form(None),
    translationModel: Optional[str] = Form(None),
    instruction: Optional[str] = Form(None),
    access_token: Optional[str] = Form(None),
    zipfile: Optional[UploadFile] = File(None),
    base_dir: Optional[str] = Form(None),
):
    """Process files either from uploaded zip or OneDrive."""
    # Initialize job
    job = JobManager.create()
    job.token = access_token

    # Normalize model names
    glossing_model = ProcessingService.normalize_model_name(glossingModel)
    translation_model = ProcessingService.normalize_model_name(translationModel)

    logger.info(f"Processing job {job.id} - glossingModel: {glossing_model}, translationModel: {translation_model}")

    # Validate required parameters
    if not language:
        job.queue.put("[ERROR] Missing language")
        return {"job_id": job.id}

    try:
        if zipfile:
            # Handle zip file upload
            tmp_dir = await ProcessingService.extract_zipfile(zipfile)
            worker = ProcessingService.create_zip_worker(
                tmp_dir, action, language, instruction,
                translation_model, glossing_model, job
            )
            job.base_dir = tmp_dir
        else:
            # Handle OneDrive processing
            if not base_dir or not access_token:
                raise HTTPException(
                    status_code=400, 
                    detail="Missing base_dir or access_token for online processing"
                )
            
            worker = ProcessingService.create_onedrive_worker(
                base_dir, action, language, instruction,
                translation_model, glossing_model, access_token, job
            )

        # Start worker process
        job.process = await ProcessingService.create_worker_process(worker.run)
        return {"job_id": job.id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create worker for job {job.id}: {e}")
        job.queue.put(f"[ERROR] Failed to initialize processing: {str(e)}")
        return {"job_id": job.id}


@router.get("/{job_id}/stream")
async def stream(job_id: str):
    """Stream job progress events via Server-Sent Events."""
    job = JobManager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        """Generate events from job queue."""
        loop = asyncio.get_event_loop()
        
        while True:
            try:
                message = await loop.run_in_executor(None, job.queue.get)
                
                # Handle special messages
                if isinstance(message, str) and message.startswith("[ZIP PATH] "):
                    job.zip_path = message.replace("[ZIP PATH] ", "").strip()
                    continue
                
                yield {"data": message}
                
                if message == "[DONE ALL]":
                    break
                    
            except Exception as e:
                logger.error(f"Error in event generator for job {job_id}: {e}")
                yield {"data": f"[ERROR] Stream error: {str(e)}"}
                break

    return EventSourceResponse(event_generator())


@router.get("/{job_id}/download")
async def download(job_id: str, background_tasks: BackgroundTasks):
    """Download processed results as zip file."""
    job = JobManager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if not job.zip_path or not os.path.exists(job.zip_path):
        raise HTTPException(status_code=404, detail="Results not ready")

    # Schedule cleanup
    background_tasks.add_task(JobCleanupService.cleanup_job, job_id, job)
    
    return FileResponse(
        path=job.zip_path,
        media_type="application/zip",
        filename=f"{job.id}_results.zip"
    )


@router.post("/cancel")
async def cancel(payload: dict = Body(...)):
    """Cancel a running job."""
    job_id = payload.get("job_id")
    if not job_id:
        raise HTTPException(status_code=400, detail="Missing job_id")
    
    job = JobManager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    try:
        # Signal cancellation
        job.queue.put("[CANCELLED]")
        job.queue.put("[DONE ALL]")
        
        # Terminate process if running
        if job.process and job.process.is_alive():
            job.process.terminate()
            job.process.join(timeout=5)  # Wait up to 5 seconds
            
            if job.process.is_alive():
                logger.warning(f"Force killing process for job {job_id}")
                job.process.kill()
    
    except Exception as e:
        logger.error(f"Error cancelling job {job_id}: {e}")
    
    finally:
        JobManager.remove(job_id)
    
    return {"status": "cancelled"}


@router.get("/models/{task}")
async def list_models(task: str):
    """List available models for a given task."""
    if task not in VALID_TASKS:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid task. Must be one of: {', '.join(VALID_TASKS)}"
        )

    dir_path = MODELS_BASE / task
    
    if not dir_path.exists():
        logger.warning(f"Models directory not found: {dir_path}")
        return {"models": []}
    
    if not dir_path.is_dir():
        logger.error(f"Models path is not a directory: {dir_path}")
        return {"models": []}

    try:
        models = [d.name for d in dir_path.iterdir() if d.is_dir()]
        models.sort()  # Return sorted list for consistency
        return {"models": models}
    except Exception as e:
        logger.error(f"Error listing models in {dir_path}: {e}")
        return {"models": []}