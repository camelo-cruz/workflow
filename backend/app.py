import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from routers.auth      import router as auth_router
from routers.inference import router as inference_router
from routers.train     import router as train_router

# 1) DEV flag from env
DEV = os.getenv("DEV", "0") == "1"

# 2) Resolve to your Vite dist folder
BASE_DIR      = Path(__file__).resolve().parent       # .../backend/app
PROJECT_ROOT  = BASE_DIR.parent                       # .../backend
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"    # vite’s default

if not DEV and not FRONTEND_DIST.exists():
    raise RuntimeError(f"Couldn’t find dist at {FRONTEND_DIST!r}")

app = FastAPI()

# 4) Mount your API routers under /api
app.include_router(auth_router,      prefix="/api/auth")
app.include_router(inference_router, prefix="/api/inference")
app.include_router(train_router,     prefix="/api/train")

# 3) In dev: allow your React dev-server to call the API
if DEV:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8080"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# 5) In prod: one catch-all GET to serve files or fallback to index.html
if not DEV:
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        # full_path is e.g. "assets/index-xyz.js", "zas_logo.jpg", "inference", etc.
        file_path = FRONTEND_DIST / full_path

        # 5a) If this exact file exists, serve it
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))

        # 5b) Otherwise fall back to index.html
        return FileResponse(str(FRONTEND_DIST / "index.html"))

# 6) Run:
#    # dev (frontend hot-reload on 8080, API on 8000):
#    DEV=1 uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
#
#    # prod (after `cd frontend && npm run build` → dist/):
#    uvicorn app.main:app --host 0.0.0.0 --port 8000
