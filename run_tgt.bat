@echo off
REM ==== Start Nginx ====
cd /d C:\nginx
start nginx

REM ==== Switch to project root ====
cd /d C:\Users\camelo.cruz\Documents\GitHub\TGT

REM ==== Activate conda env ====
REM make sure you’ve run "conda init" so this works
call conda activate tgt

REM ==== Ensure logs folder exists ====
if not exist ".\logs" mkdir ".\logs"

REM ==== Launch Uvicorn ====
cd /d C:\Users\camelo.cruz\Documents\GitHub\TGT\backend
python -m uvicorn app:app --host 127.0.0.1 --port 8000 ^
    >> "..\logs\uvicorn.log" 2>&1

REM ==== Script ends when Uvicorn exits ====
exit
