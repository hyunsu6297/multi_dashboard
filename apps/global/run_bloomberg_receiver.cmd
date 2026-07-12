@echo off
setlocal

set "APP_DIR=%~dp0"
set "SERVER=%APP_DIR%global_dashboard_server.py"
set "HOST=127.0.0.1"
set "PORT=8766"
set "BLP_HOST=localhost"
set "BLP_PORT=8194"
set "CODEX_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

cd /d "%APP_DIR%"

echo Global Dashboard Bloomberg receiver
echo.
echo Dashboard URL : http://%HOST%:%PORT%/
echo API URL       : http://%HOST%:%PORT%/api/emp-market
echo Bloomberg Terminal must be logged in before update.
echo Keep this window open while using Bloomberg update.
echo.

if not exist "%SERVER%" (
  echo ERROR: server file not found.
  echo %SERVER%
  set "EXIT_CODE=1"
  goto done
)

if defined GLOBAL_DASHBOARD_PYTHON (
  if exist "%GLOBAL_DASHBOARD_PYTHON%" (
    echo Using GLOBAL_DASHBOARD_PYTHON
    "%GLOBAL_DASHBOARD_PYTHON%" "%SERVER%" --host %HOST% --port %PORT% --provider bloomberg --blp-host %BLP_HOST% --blp-port %BLP_PORT%
    set "EXIT_CODE=%ERRORLEVEL%"
    goto done
  )
)

if exist "%CODEX_PYTHON%" (
  echo Using bundled Python
  "%CODEX_PYTHON%" "%SERVER%" --host %HOST% --port %PORT% --provider bloomberg --blp-host %BLP_HOST% --blp-port %BLP_PORT%
  set "EXIT_CODE=%ERRORLEVEL%"
  goto done
)

py -3 -c "import sys" >nul 2>nul
if not errorlevel 1 (
  echo Using py launcher
  py -3 "%SERVER%" --host %HOST% --port %PORT% --provider bloomberg --blp-host %BLP_HOST% --blp-port %BLP_PORT%
  set "EXIT_CODE=%ERRORLEVEL%"
  goto done
)

python -c "import sys" >nul 2>nul
if not errorlevel 1 (
  echo Using python from PATH
  python "%SERVER%" --host %HOST% --port %PORT% --provider bloomberg --blp-host %BLP_HOST% --blp-port %BLP_PORT%
  set "EXIT_CODE=%ERRORLEVEL%"
  goto done
)

echo ERROR: Python was not found.
echo Install Python or set GLOBAL_DASHBOARD_PYTHON to python.exe with blpapi.
set "EXIT_CODE=1"

:done
echo.
if not "%EXIT_CODE%"=="0" echo Receiver stopped. Exit code: %EXIT_CODE%
pause
exit /b %EXIT_CODE%
