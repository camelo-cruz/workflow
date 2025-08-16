from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from routers.auth import router as auth_router
from routers.inference.inference import router as inference_router
from routers.training.train import router as train_router


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"

app = FastAPI()

app.include_router(auth_router, prefix="/api/auth")
app.include_router(inference_router, prefix="/api/inference")
app.include_router(train_router, prefix="/api/train")


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(full_path: str):
    candidate = FRONTEND_DIST / full_path
    index = FRONTEND_DIST / "index.html"

    if candidate.is_file():
        return FileResponse(candidate)

    # Fallback for "/", directories, and unknown client-side routes
    if index.is_file():
        return FileResponse(index)

    # If your build is missing index.html, return a real 404 instead of "null"
    raise HTTPException(status_code=404, detail="Frontend build not found")
