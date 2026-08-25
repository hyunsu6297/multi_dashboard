param(
    [int]$HistoryDays = 45,
    [double]$RequestDelay = 0.7,
    [double]$Timeout = 20.0,
    [string]$StartDate = "",
    [string]$EndDate = "",
    [switch]$SkipBackfill
)

$ErrorActionPreference = "Stop"

$RootDir = $PSScriptRoot
$ParentDir = Split-Path -Parent $RootDir
$Python = "C:\Users\infomax\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$SupabaseKeyFile = Join-Path $RootDir "supabase_service_key.dat"
$StockDir = Join-Path $RootDir "apps\stock"
$MezzanineDir = Join-Path $RootDir "apps\mezzanine"
$Updater = Join-Path $MezzanineDir "update_delta_history.py"

function FirstFile($Directory, $Pattern) {
    if (-not (Test-Path -LiteralPath $Directory)) {
        return $null
    }
    return Get-ChildItem -Path (Join-Path $Directory $Pattern) -File -ErrorAction SilentlyContinue | Select-Object -First 1
}

if (-not (Test-Path -LiteralPath $Python)) {
    $Python = "python"
}
if (-not (Test-Path -LiteralPath $Updater)) {
    throw "Mezzanine delta updater not found: $Updater"
}

$CredentialRoots = @($RootDir, $StockDir, $MezzanineDir)
if (Test-Path -LiteralPath $ParentDir) {
    $SiblingDirs = Get-ChildItem -LiteralPath $ParentDir -Directory -ErrorAction SilentlyContinue
    foreach ($Dir in $SiblingDirs) {
        $CredentialRoots += $Dir.FullName
    }
}

$AppKeyFile = $null
$SecretKeyFile = $null
foreach ($Dir in $CredentialRoots) {
    $CandidateAppKey = FirstFile $Dir "*_appkey.txt"
    $CandidateSecretKey = FirstFile $Dir "*_secretkey.txt"
    if ($CandidateAppKey -and $CandidateSecretKey) {
        $AppKeyFile = $CandidateAppKey
        $SecretKeyFile = $CandidateSecretKey
        break
    }
}

if (-not $AppKeyFile -or -not $SecretKeyFile) {
    throw "Kiwoom credential files were not found."
}

$env:KIWOOM_APPKEY = (Get-Content -Raw -LiteralPath $AppKeyFile.FullName).Trim()
$env:KIWOOM_SECRETKEY = (Get-Content -Raw -LiteralPath $SecretKeyFile.FullName).Trim()
$env:SUPABASE_URL = "https://esqakvzvchcunhzjlyry.supabase.co"

if (-not $env:SUPABASE_SERVICE_ROLE_KEY) {
    if (Test-Path -LiteralPath $SupabaseKeyFile) {
        $EncryptedKey = (Get-Content -Raw -LiteralPath $SupabaseKeyFile).Trim()
        $SecureKey = $EncryptedKey | ConvertTo-SecureString
    }
    else {
        Write-Host "Supabase service role key setup is required once."
        $SecureKey = Read-Host "Paste the Supabase secret/service_role key" -AsSecureString
        $EncryptedKey = $SecureKey | ConvertFrom-SecureString
        [IO.File]::WriteAllText($SupabaseKeyFile, $EncryptedKey, [Text.Encoding]::ASCII)
    }

    $Pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureKey)
    try {
        $env:SUPABASE_SERVICE_ROLE_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Pointer)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Pointer)
    }
}

Write-Host "Mezzanine daily price and delta updater"
Write-Host "Updater: $Updater"
Write-Host "Credentials: $($AppKeyFile.DirectoryName)"
Write-Host "Mode: restore Supabase inputs, update missing dates only"
Write-Host ""

$UpdaterArgs = @(
    $Updater,
    "--restore-inputs",
    "--missing-only",
    "--history-days", $HistoryDays,
    "--request-delay", $RequestDelay,
    "--timeout", $Timeout
)
if ($StartDate) {
    $UpdaterArgs += @("--start-date", $StartDate)
}
if ($EndDate) {
    $UpdaterArgs += @("--end-date", $EndDate)
}
if ($SkipBackfill) {
    $UpdaterArgs += "--skip-backfill"
}

Push-Location $RootDir
try {
    & $Python @UpdaterArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Mezzanine delta updater exited with code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
    Remove-Item Env:KIWOOM_APPKEY -ErrorAction SilentlyContinue
    Remove-Item Env:KIWOOM_SECRETKEY -ErrorAction SilentlyContinue
    Remove-Item Env:SUPABASE_SERVICE_ROLE_KEY -ErrorAction SilentlyContinue
}
