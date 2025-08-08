@echo off
REM Set UTF-8 code page for proper character encoding
chcp 65001 >nul

REM ==== Kill any existing Nginx processes ====
taskkill /f /im nginx.exe >nul 2>&1

REM ==== Start Nginx ====
cd /d C:\nginx
start nginx

REM ==== Switch to project root ====
cd /d C:\Users\camelo.cruz\Documents\GitHub\TGT

REM ==== Activate conda env ====
call conda activate tgt

REM ==== Ensure logs folder exists ====
if not exist ".\logs" mkdir ".\logs"

REM ==== Set Python UTF-8 environment variables ====
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

REM ==== Launch Uvicorn ====
cd /d C:\Users\camelo.cruz\Documents\GitHub\TGT\backend
python -m uvicorn app:app --host 127.0.0.1 --port 8000 ^
    >> "..\logs\uvicorn.log" 2>&1

exit