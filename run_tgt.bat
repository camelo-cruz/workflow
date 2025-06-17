@echo off

REM Change to your project directory
cd /d C:\Users\camelo.cruz\Documents\GitHub\workflow\tgt

REM Activate the Conda environment
CALL C:\Users\camelo.cruz\Documents\GitHub\workflow\tgt\tgt\Scripts\activate.bat

REM Run Uvicorn using the environment's Python interpreter
start "" /min python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000

exit
