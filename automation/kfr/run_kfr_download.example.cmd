@echo off
setlocal
cd /d "%~dp0"

if not defined KFR_APP_KEY_ID (
  echo KFR_APP_KEY_ID environment variable is required.
  exit /b 1
)
if not defined KFR_APP_KEY_SECRET (
  echo KFR_APP_KEY_SECRET environment variable is required.
  exit /b 1
)

python kfr_partner_api_download.py --output-dir "%TEMP%\kfr_partner_api" %*

