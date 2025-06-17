@echo off
title Uvicorn + nginx Launcher
set LOGFILE=%~dp0uvicorn-log.txt

REM Activate the virtual environment
CALL C:\Users\camelo.cruz\Documents\GitHub\workflow\tgt-venv\Scripts\activate.bat

REM Start nginx in the background
REM --------------------------------
REM Option A: If you installed nginx by unzipping into C:\nginx\
pushd C:\nginx
start "" nginx.exe
popd

REM Option B: If you installed nginx as a Windows service
REM net start nginx
REM --------------------------------

REM Change to project directory
cd /d C:\Users\camelo.cruz\Documents\GitHub\workflow\tgt

:loop
echo [%date% %time%] Starting Uvicorn... >> %LOGFILE%
python.exe -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload >> %LOGFILE% 2>&1
echo [%date% %time%] Uvicorn stopped. Restarting in 5s... >> %LOGFILE%
timeout /t 5
goto loop