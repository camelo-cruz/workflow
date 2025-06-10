@echo off
title Uvicorn Server
set LOGFILE=%~dp0uvicorn-log.txt

REM Activate the virtual environment
CALL C:\Users\camelo.cruz\Documents\GitHub\workflow\tgt-venv\Scripts\activate.bat

REM Change to project directory
cd /d C:\Users\camelo.cruz\Documents\GitHub\workflow\tgt

:loop
echo [%date% %time%] Starting Uvicorn... >> %LOGFILE%
python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload >> %LOGFILE% 2>&1
echo [%date% %time%] Uvicorn stopped. Restarting in 5s... >> %LOGFILE%
timeout /t 5
goto loop

