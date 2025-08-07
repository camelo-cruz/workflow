import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from routers.auth import router as auth_router
from routers.inference.inference import router as inference_router
from routers.training.train import router as train_router


# 2) Resolve to your Vite dist folder
BASE_DIR = Path(__file__).resolve().parent # .../backend/app
PROJECT_ROOT = BASE_DIR.parent # .../backend
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist" # vite’s default

app = FastAPI()

# 4) Mount your API routers under /api
app.include_router(auth_router, prefix="/api/auth")
app.include_router(inference_router, prefix="/api/inference")
app.include_router(train_router, prefix="/api/train")


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(full_path: str):
    # full_path is e.g. "assets/index-xyz.js", "zas_logo.jpg", "inference", etc.
    file_path = FRONTEND_DIST / full_path

    # 5a) If this exact file exists, serve it
    if file_path.exists() and file_path.is_file():
        return FileResponse(str(file_path))

    # 5b) Otherwise fall back to index.html
    return FileResponse(str(FRONTEND_DIST / "index.html"))