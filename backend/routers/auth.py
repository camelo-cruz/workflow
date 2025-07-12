import os
import msal
from pathlib import Path
from dotenv import load_dotenv
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")
router = APIRouter()

TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
if not (TENANT_ID and CLIENT_ID and CLIENT_SECRET):
    envf = Path(__file__).parent.parent / "materials" / "secrets.env"
    if envf.exists():
        load_dotenv(envf)
        TENANT_ID = os.getenv("TENANT_ID")
        CLIENT_ID = os.getenv("CLIENT_ID")
        CLIENT_SECRET = os.getenv("CLIENT_SECRET")
if not (TENANT_ID and CLIENT_ID and CLIENT_SECRET):
    raise ValueError("Missing OneDrive OAuth credentials")

SCOPES    = ["Files.ReadWrite.All", "User.Read"]
AUTH_URL  = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"

def _build_msal_app(cache=None):
    return msal.ConfidentialClientApplication(
        CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
        client_credential=CLIENT_SECRET,
        token_cache=cache
    )

@router.get("/start")
async def start_onedrive_auth(request: Request):
    host   = request.headers.get("host")
    scheme = "http" if host.startswith(("localhost", "127.0.0.1")) else "https"
    redirect_uri = f"{scheme}://{host}/api/auth/redirect"

    msal_app = _build_msal_app()
    auth_url = msal_app.get_authorization_request_url(
        scopes=SCOPES,
        redirect_uri=redirect_uri,
        response_mode="query",
    )
    return RedirectResponse(url=auth_url, status_code=302)


@router.get("/redirect")
async def onedrive_auth_redirect(request: Request):
    code = request.query_params.get("code")
    if not code:
        return JSONResponse({"error": "No code in callback"}, status_code=400)

    host   = request.headers.get("host")
    scheme = "http" if host.startswith(("localhost", "127.0.0.1")) else "https"
    redirect_uri = f"{scheme}://{host}/api/auth/redirect"

    msal_app = _build_msal_app()
    result = msal_app.acquire_token_by_authorization_code(
        code,
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )

    token = result.get("access_token")
    if not token:
        return JSONResponse({"error": "Token error", "details": result}, status_code=400)

    # Build a frontend URL that Vite will serve at /auth/success
    host   = request.headers.get("host")
    host = "localhost:8080"
    scheme = "http" if host.startswith(("localhost", "127.0.0.1")) else "https"
    frontend_success = f"{scheme}://{host}/success-auth#token={token}"

    return RedirectResponse(url=frontend_success, status_code=302)