@echo off

REM Change to your project directory
cd /d C:\Users\camelo.cruz\Desktop\workflow

REM Activate the Conda environment
CALL C:\Users\camelo.cruz\Desktop\workflow\tgt-venv\Scripts\activate.bat

REM Change to backend directory
cd /d C:\Users\camelo.cruz\Desktop\workflow\backend

REM Ensure the log directory exists
if not exist "..\logs" mkdir "..\logs"

REM Run Uvicorn using the environment's Python interpreter, redirecting output to a log file
start "" /min cmd /c "python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000  >> ..\logs\uvicorn.log 2>&1"

exit
