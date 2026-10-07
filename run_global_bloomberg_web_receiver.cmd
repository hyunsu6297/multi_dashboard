@echo off
setlocal
cd /d "%~dp0apps\global"
if not defined SUPABASE_SERVICE_ROLE_KEY (
  echo SUPABASE_SERVICE_ROLE_KEY is not set for this session.
  echo Add it to the Windows user environment and open a new CMD window.
  pause
  exit /b 1
)
if not defined SUPABASE_URL set "SUPABASE_URL=https://esqakvzvchcunhzjlyry.supabase.co"
echo Starting Bloomberg receiver for the web global dashboard...
python publish_bloomberg_market.py
if errorlevel 1 (
  echo Receiver stopped with an error.
  pause
)
