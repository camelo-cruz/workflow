@echo off
REM — Switch to your project root
cd /d C:\Users\camelo.cruz\Documents\GitHub\workflow

REM — Activate your virtual environment
CALL tgt-venv\Scripts\activate.bat

REM — Move into backend and ensure logs exist
cd backend
if not exist "..\logs" mkdir "..\logs"

REM — Launch Uvicorn inline; Scheduler will hide the console window
python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000 ^
    >> "..\logs\uvicorn.log" 2>&1

REM — When python.exe (i.e. Uvicorn) exits, the script ends, too
exit
