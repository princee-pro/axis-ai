# stop_jarvis.ps1 — Phase 7.4
# Stops the Jarvis Bridge server gracefully using the PID lockfile.
# Usage: .\scripts\stop_jarvis.ps1

$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$LockFile    = Join-Path $ProjectRoot "storage\runtime\jarvis.pid"

if (-not (Test-Path $LockFile)) {
    Write-Host "[STOP] No lockfile found. Jarvis may not be running." -ForegroundColor Yellow
    exit 0
}

$pid_val = Get-Content $LockFile -ErrorAction SilentlyContinue
$proc    = Get-Process -Id $pid_val -ErrorAction SilentlyContinue

if ($proc) {
    Write-Host "[STOP] Stopping Jarvis (PID $pid_val)..." -ForegroundColor Cyan
    try {
        # Prefer graceful stop via taskkill (sends CTRL_C on Windows equivalent)
        taskkill /PID $pid_val /F | Out-Null
        Write-Host "[STOP] Jarvis stopped successfully."
    } catch {
        Write-Host "[STOP] Failed to stop process: $_" -ForegroundColor Red
    }
} else {
    Write-Host "[STOP] Process $pid_val not running. Removing stale lockfile."
}

# Clean up lockfile
if (Test-Path $LockFile) { Remove-Item $LockFile -Force }
Write-Host "[STOP] Lockfile removed."
