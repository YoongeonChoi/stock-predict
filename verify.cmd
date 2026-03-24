@echo off
setlocal

set "ROOT=%~dp0"
set "VENV_PYTHON=%ROOT%venv\Scripts\python.exe"
set "VERIFY=%ROOT%verify.py"

if not exist "%VERIFY%" (
  echo [fail] Missing verify launcher: %VERIFY%
  exit /b 1
)

if exist "%VENV_PYTHON%" (
  "%VENV_PYTHON%" "%VERIFY%" %*
  exit /b %ERRORLEVEL%
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0verify.ps1" %*
exit /b %ERRORLEVEL%
