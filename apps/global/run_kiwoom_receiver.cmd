@echo off
setlocal

set "APP_DIR=%~dp0"
set "PUBLISHER=%APP_DIR%publish_kiwoom_market.py"
set "CYCLE_SECONDS=20"
set "CODEX_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

cd /d "%APP_DIR%"

echo Global Dashboard Kiwoom Supabase receiver
echo.
echo Mode          : domestic KS auto refresh + Supabase request queue
echo Domestic cycle: %CYCLE_SECONDS% seconds
echo Request queue : pending global refreshes are processed on this PC
echo.
echo Required environment variables:
echo   KIWOOM_APPKEY
echo   KIWOOM_SECRETKEY
echo   SUPABASE_SERVICE_ROLE_KEY
echo.
echo Optional:
echo   KIWOOM_ACCESS_TOKEN   ^(if you want to reuse an issued token^)
echo   KIWOOM_BASE_URL       ^(default: https://api.kiwoom.com^)
echo   SUPABASE_URL          ^(default: production project^)
echo.

if "%KIWOOM_APPKEY%"=="" (
  if "%KIWOOM_ACCESS_TOKEN%"=="" (
    echo ERROR: KIWOOM_APPKEY is not set.
    echo Example:
    echo   setx KIWOOM_APPKEY "your_appkey"
    echo   setx KIWOOM_SECRETKEY "your_secretkey"
    set "EXIT_CODE=1"
    goto done
  )
)

if "%KIWOOM_SECRETKEY%"=="" (
  if "%KIWOOM_ACCESS_TOKEN%"=="" (
    echo ERROR: KIWOOM_SECRETKEY is not set.
    set "EXIT_CODE=1"
    goto done
  )
)

if "%SUPABASE_SERVICE_ROLE_KEY%"=="" (
  echo ERROR: SUPABASE_SERVICE_ROLE_KEY is not set.
  echo This key is only for this local receiver. Never put it in browser code.
  set "EXIT_CODE=1"
  goto done
)

if not exist "%PUBLISHER%" (
  echo ERROR: publisher file not found.
  echo %PUBLISHER%
  set "EXIT_CODE=1"
  goto done
)

if defined GLOBAL_DASHBOARD_PYTHON (
  if exist "%GLOBAL_DASHBOARD_PYTHON%" (
    echo Using GLOBAL_DASHBOARD_PYTHON
    "%GLOBAL_DASHBOARD_PYTHON%" "%PUBLISHER%" --domestic-cycle-seconds %CYCLE_SECONDS%
    set "EXIT_CODE=%ERRORLEVEL%"
    goto done
  )
)

if exist "%CODEX_PYTHON%" (
  echo Using bundled Python
  "%CODEX_PYTHON%" "%PUBLISHER%" --domestic-cycle-seconds %CYCLE_SECONDS%
  set "EXIT_CODE=%ERRORLEVEL%"
  goto done
)

py -3 -c "import sys" >nul 2>nul
if not errorlevel 1 (
  echo Using py launcher
  py -3 "%PUBLISHER%" --domestic-cycle-seconds %CYCLE_SECONDS%
  set "EXIT_CODE=%ERRORLEVEL%"
  goto done
)

python -c "import sys" >nul 2>nul
if not errorlevel 1 (
  echo Using python from PATH
  python "%PUBLISHER%" --domestic-cycle-seconds %CYCLE_SECONDS%
  set "EXIT_CODE=%ERRORLEVEL%"
  goto done
)

echo ERROR: Python was not found.
echo Install Python or set GLOBAL_DASHBOARD_PYTHON to python.exe.
set "EXIT_CODE=1"

:done
echo.
if not "%EXIT_CODE%"=="0" echo Receiver stopped. Exit code: %EXIT_CODE%
pause
exit /b %EXIT_CODE%
