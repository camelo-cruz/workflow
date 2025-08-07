import os
import shutil
import tempfile
from typing import Optional
import uuid
import logging
from pathlib import Path
from zipfile import ZipFile
from fastapi import APIRouter, HTTPException, UploadFile
from multiprocessing import Process, Queue, Event
from multiprocessing import Process

from routers.inference.inference_workers import OneDriveWorker, ZipWorker

logger = logging.getLogger(__name__)
router = APIRouter()

MODELS_BASE = Path(__file__).resolve().parent.parent / "models"
DEFAULT_MODEL = "Default"

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


class ProcessingService:
    """Service class to handle processing logic."""
    
    @staticmethod
    async def create_worker_process(process_fn) -> Process:
        """Create and start a worker process."""
        proc = Process(target=process_fn, daemon=True)
        proc.start()
        return proc
    
    @staticmethod
    def normalize_model_name(model: Optional[str]) -> Optional[str]:
        """Normalize model name, converting 'Default' to None."""
        return None if model == DEFAULT_MODEL else model
    
    @staticmethod
    async def extract_zipfile(zipfile: UploadFile) -> str:
        """Extract uploaded zip file to temporary directory."""
        tmp_dir = tempfile.mkdtemp()
        archive_path = Path(tmp_dir) / "upload.zip"
        
        try:
            contents = await zipfile.read()
            archive_path.write_bytes(contents)
            
            with ZipFile(archive_path, 'r') as archive:
                archive.extractall(tmp_dir)
            
            archive_path.unlink()
            return tmp_dir
            
        except Exception as e:
            # Cleanup on failure
            if archive_path.exists():
                archive_path.unlink()
            shutil.rmtree(tmp_dir, ignore_errors=True)
            raise HTTPException(status_code=400, detail=f"Failed to extract zip file: {str(e)}")
    
    @staticmethod
    def create_zip_worker(tmp_dir: str, action: str, language: str, 
                         instruction: Optional[str], translation_model: Optional[str], 
                         glossing_model: Optional[str], job) -> ZipWorker:
        """Create a ZipWorker instance."""
        return ZipWorker(
            tmp_dir, action, language, instruction,
            translation_model, glossing_model, job
        )
    
    @staticmethod
    def create_onedrive_worker(base_dir: str, action: str, language: str,
                              instruction: Optional[str], translation_model: Optional[str],
                              glossing_model: Optional[str], access_token: str, job) -> OneDriveWorker:
        """Create an OneDriveWorker instance."""
        return OneDriveWorker(
            base_dir, action, language, instruction,
            translation_model, glossing_model, access_token, job
        )


class JobCleanupService:
    """Service class to handle job cleanup operations."""
    
    @staticmethod
    def cleanup_job(job_id: str, job):
        """Clean up job resources including files and directories."""
        try:
            if job.zip_path and os.path.exists(job.zip_path):
                os.remove(job.zip_path)
        except OSError as e:
            logger.warning(f"Failed to delete zip file {job.zip_path}: {e}")
        
        if job.base_dir and os.path.isdir(job.base_dir):
            try:
                shutil.rmtree(job.base_dir, ignore_errors=True)
            except Exception as e:
                logger.warning(f"Failed to remove base directory {job.base_dir}: {e}")
        
        JobManager.remove(job_id)