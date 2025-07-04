import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from routers.auth import router as auth_router
from routers.inference import router as inference_router
from routers.train import router as train_router

# Decide by an env var—set DEV=1 in your shell when local‐deving.
DEV = True
BASE_DIR = Path(__file__).parent

app = FastAPI()

# Always include your API routers:
app.include_router(auth_router, prefix="/auth")
app.include_router(inference_router, prefix="/inference")
app.include_router(train_router, prefix="/train")

if DEV:
    # In dev, allow your React app (on :8080) to call your backend (on :8000)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8080"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # No StaticFiles mount—Vite handles the SPA on port 8080
else:
    # In prod, serve the built React app under FastAPI
    FRONTEND_DIST = BASE_DIR.parent / "frontend" / "dist"
    app.mount(
        "/",
        StaticFiles(directory=str(FRONTEND_DIST), html=True),
        name="frontend",
    )
    # Optionally, if you want a catch-all to index.html:
    @app.get("/{full_path:path}")
    async def serve_index(full_path: str):
        return FileResponse(FRONTEND_DIST / "index.html")
