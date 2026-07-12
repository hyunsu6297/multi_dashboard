@echo off
setlocal

set "APP_DIR=%~dp0"
set "SERVER=%APP_DIR%global_dashboard_server.py"
set "HOST=127.0.0.1"
set "PORT=8766"
set "CODEX_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

cd /d "%APP_DIR%"

echo Global Dashboard Kiwoom local API server
echo.
echo Dashboard URL : http://%HOST%:%PORT%/
echo API URL       : http://%HOST%:%PORT%/api/emp-market
echo Provider      : Kiwoom REST API
echo.
echo This is for local manual testing. For shared deployed prices, use:
echo   run_global_kiwoom_receiver.cmd
echo.

if defined GLOBAL_DASHBOARD_PYTHON (
  if exist "%GLOBAL_DASHBOARD_PYTHON%" (
    "%GLOBAL_DASHBOARD_PYTHON%" "%SERVER%" --host %HOST% --port %PORT% --provider kiwoom
    set "EXIT_CODE=%ERRORLEVEL%"
    goto done
  )
)

if exist "%CODEX_PYTHON%" (
  "%CODEX_PYTHON%" "%SERVER%" --host %HOST% --port %PORT% --provider kiwoom
  set "EXIT_CODE=%ERRORLEVEL%"
  goto done
)

py -3 -c "import sys" >nul 2>nul
if not errorlevel 1 (
  py -3 "%SERVER%" --host %HOST% --port %PORT% --provider kiwoom
  set "EXIT_CODE=%ERRORLEVEL%"
  goto done
)

python -c "import sys" >nul 2>nul
if not errorlevel 1 (
  python "%SERVER%" --host %HOST% --port %PORT% --provider kiwoom
  set "EXIT_CODE=%ERRORLEVEL%"
  goto done
)

echo ERROR: Python was not found.
set "EXIT_CODE=1"

:done
echo.
if not "%EXIT_CODE%"=="0" echo Local API stopped. Exit code: %EXIT_CODE%
pause
exit /b %EXIT_CODE%
