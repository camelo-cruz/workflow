import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from fastapi.staticfiles import StaticFiles
from routers.auth      import router as auth_router
from routers.inference import router as inference_router
from routers.train     import router as train_router

# 1) DEV flag from environment
DEV = False

# 2) Compute paths
BASE_DIR      = Path(__file__).resolve().parent      # backend/app
PROJECT_ROOT  = BASE_DIR.parent
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"   # vite output

if not DEV:
    if not FRONTEND_DIST.exists():
        raise RuntimeError(f"No frontend dist folder at {FRONTEND_DIST!r}")

# 3) Create FastAPI app
app = FastAPI()

# 4) In dev: allow CORS so your React server (http://localhost:8080) can hit this API
if DEV:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8080"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# 5) Include your API routers (they handle POST/PUT/DELETE on /inference, etc.)
app.include_router(auth_router,      prefix="/auth")
app.include_router(inference_router, prefix="/inference")
app.include_router(train_router,     prefix="/train")

# 6) In prod: serve static files & SPA fallback
if not DEV:
    # 6a) Serve any real file in dist/ (CSS, JS, images…)
    app.mount(
        "/static",
        StaticFiles(directory=str(FRONTEND_DIST)),
        name="static",
    )

    # 6b) Root path
    @app.get("/", include_in_schema=False)
    async def serve_index():
        return FileResponse(str(FRONTEND_DIST / "index.html"))

    # 6c) Catch-all GET for client-side routing (e.g. /inference, /train, /foo/bar)
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        file_path = FRONTEND_DIST / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(FRONTEND_DIST / "index.html"))

# 7) To run:
#    # dev: front on 8080, back on 8000
#    DEV=1 uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
#
#    # prod (after `cd frontend && npm run build`):
#    uvicorn app.main:app --host 0.0.0.0 --port 8000
