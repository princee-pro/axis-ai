# start_jarvis.ps1 — Phase 7.4
# Starts the Jarvis Bridge server in the background and logs output.
# Usage: .\scripts\start_jarvis.ps1

$ErrorActionPreference = "Stop"

$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$LogFile     = Join-Path $ProjectRoot "logs\jarvis_server.log"
$LockFile    = Join-Path $ProjectRoot "storage\runtime\jarvis.pid"

# Ensure log directory exists
New-Item -ItemType Directory -Force -Path (Split-Path $LogFile) | Out-Null

# Check for running instance via lockfile
if (Test-Path $LockFile) {
    $pid_val = Get-Content $LockFile -ErrorAction SilentlyContinue
    $proc    = Get-Process -Id $pid_val -ErrorAction SilentlyContinue
    if ($proc) {
        Write-Host "[START] Jarvis is already running (PID $pid_val). Exiting." -ForegroundColor Yellow
        Write-Host "  Use: .\scripts\stop_jarvis.ps1  to stop it first."
        exit 1
    } else {
        Write-Host "[START] Stale lockfile removed (PID $pid_val was not running)."
        Remove-Item $LockFile -Force
    }
}

$StdOutLog  = Join-Path $ProjectRoot "logs\jarvis_stdout.log"
$StdErrLog  = Join-Path $ProjectRoot "logs\jarvis_stderr.log"

Write-Host "[START] Launching Jarvis server..." -ForegroundColor Cyan
$proc = Start-Process python `
    -ArgumentList "-m jarvis_ai.mobile.server" `
    -WorkingDirectory $ProjectRoot `
    -RedirectStandardOutput $StdOutLog `
    -RedirectStandardError  $StdErrLog `
    -PassThru `
    -WindowStyle Hidden

Write-Host "[START] Jarvis started (PID $($proc.Id))."
Write-Host "  Stdout: $StdOutLog"
Write-Host "  Stderr: $StdErrLog"
Write-Host "  Health: curl http://127.0.0.1:8000/health -H 'X-Jarvis-Token: YOUR_TOKEN'"
