@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_mezzanine_delta_update.ps1" %*
if errorlevel 1 (
  echo.
  echo Mezzanine delta updater stopped with an error.
  pause
)
