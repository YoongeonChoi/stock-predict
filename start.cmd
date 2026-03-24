@echo off
setlocal

set "ROOT=%~dp0"
set "VENV_PYTHON=%ROOT%venv\Scripts\python.exe"
set "LAUNCHER=%ROOT%start.py"

if not exist "%LAUNCHER%" (
  echo [fail] Missing launcher: %LAUNCHER%
  exit /b 1
)

if exist "%VENV_PYTHON%" (
  "%VENV_PYTHON%" "%LAUNCHER%" %*
  exit /b %ERRORLEVEL%
)

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  py -3 "%LAUNCHER%" %*
  exit /b %ERRORLEVEL%
)

where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  python "%LAUNCHER%" %*
  exit /b %ERRORLEVEL%
)

echo [fail] Python 3.10+ or project venv is required.
exit /b 1
