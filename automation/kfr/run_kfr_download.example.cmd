@echo off
setlocal
cd /d "%~dp0"

if not defined KFROM_ID (
  echo KFROM_ID environment variable is required.
  exit /b 1
)
if not defined KFROM_PASSWORD (
  echo KFROM_PASSWORD environment variable is required.
  exit /b 1
)

python kfr_download.py %*

