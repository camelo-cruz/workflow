from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import os


from routers.auth import router as auth_router
from routers.jobs import router as jobs_router


# Load environment variables (if not already loaded)
load_dotenv(os.path.join(os.path.dirname(__file__), "materials", "secrets.env"))

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

app.include_router(auth_router)
app.include_router(jobs_router)
