@echo off
cd /d "%~dp0"
echo Starting BioTime Leave webapp on http://127.0.0.1:8000/leaves
echo Close this window (or press Ctrl+C) to stop the server.
echo.
"C:\venvs\biotime-webapp\Scripts\python.exe" -m uvicorn app.main:app --port 8000
pause
