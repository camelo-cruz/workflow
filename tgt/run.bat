@echo off
REM Initialize conda
CALL C:\Users\camelo.cruz\miniconda3\Scripts\activate.bat

REM Activate your environment
CALL conda activate tgt

REM Navigate to your app directory
cd /d C:\Users\camelo.cruz\Documents\GitHub\workflow\tgt

REM Run FastAPI with uvicorn
uvicorn app:app --host 127.0.0.1 --port 8000
