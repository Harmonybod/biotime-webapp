@echo off
rem Starts the BioTime web app. On the first run (or on a new PC) it also
rem installs Python if needed, creates the app's Python environment and
rem installs the required packages, so nothing has to be set up by hand.
setlocal EnableExtensions
cd /d "%~dp0"
title BioTime Web App

rem ZKBioTime's installer sets PYTHONHOME to its own bundled Python, which breaks
rem every other Python on the PC. Clear it for this window only (BioTime is unaffected).
set "PYTHONHOME="
set "PYTHONPATH="

set "APP_URL=http://127.0.0.1:8000/"
rem Kept outside the project folder so OneDrive doesn't sync thousands of package files.
set "VENV_DIR=%LOCALAPPDATA%\biotime-webapp\venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

echo ==== BioTime Web App ====
echo.

rem ---- 1. Python environment for the app ---------------------------------
"%VENV_PY%" -c "import sys" >nul 2>&1 && goto :have_venv

call :find_python
if not defined PY call :install_python || goto :fail
if not defined PY call :find_python
if not defined PY (
  echo Python was installed but this window can't see it yet.
  echo Close this window and double-click start-server.bat again.
  goto :fail
)

echo Creating the app's Python environment...
if exist "%VENV_DIR%" rmdir /s /q "%VENV_DIR%"
%PY% -m venv "%VENV_DIR%" || goto :fail

:have_venv
rem ---- 2. Packages: install when missing or when requirements.txt changed --
fc /b "requirements.txt" "%VENV_DIR%\requirements.installed.txt" >nul 2>&1 && goto :have_packages
echo Installing required packages (first run only, this takes a minute or two)...
"%VENV_PY%" -m pip install --disable-pip-version-check -r requirements.txt || goto :fail
copy /y "requirements.txt" "%VENV_DIR%\requirements.installed.txt" >nul
:have_packages

rem ---- 3. Settings file ----------------------------------------------------
if not exist ".env" copy ".env.example" ".env" >nul

rem ---- 4. Run ---------------------------------------------------------------
echo.
echo Starting on %APP_URL%  - your browser will open shortly.
echo Close this window (or press Ctrl+C) to stop the server.
echo.
start "" /b powershell -NoProfile -Command "Start-Sleep -Seconds 4; Start-Process '%APP_URL%'"
"%VENV_PY%" -m uvicorn app.main:app --port 8000
pause
exit /b 0


:find_python
rem Sets PY to a Python 3.10-3.12 command (the versions the pinned packages support).
set "PY="
call :try_python py -3.12
call :try_python py -3.11
call :try_python py -3.10
call :try_python python
call :try_python "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
call :try_python "%ProgramFiles%\Python312\python.exe"
exit /b 0

:try_python
if defined PY exit /b 0
%* -c "import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 12) else 1)" >nul 2>&1 && set "PY=%*"
exit /b 0

:install_python
echo Python 3.12 was not found on this PC. Installing it now (this can take a few minutes)...
echo.
where winget >nul 2>&1
if not errorlevel 1 (
  winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
  call :find_python
  if defined PY exit /b 0
)
echo Downloading the Python installer from python.org...
set "PY_INSTALLER=%TEMP%\python-3.12-installer.exe"
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = 'Tls12'; Invoke-WebRequest -UseBasicParsing 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' -OutFile '%PY_INSTALLER%'" || exit /b 1
echo Installing Python...
"%PY_INSTALLER%" /quiet InstallAllUsers=0 InstallLauncherAllUsers=0 PrependPath=1 Include_test=0 || exit /b 1
del "%PY_INSTALLER%" >nul 2>&1
call :find_python
exit /b 0

:fail
echo.
echo Setup did not finish. See the messages above.
echo Check the internet connection, then run start-server.bat again.
pause
exit /b 1
