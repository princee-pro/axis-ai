# check_jarvis.ps1 - Phase 7.4
# Shows current Jarvis server status: lock state, process health, readiness.
# Usage: .\scripts\check_jarvis.ps1 [YOUR_OWNER_TOKEN]

param([string]$Token = $env:JARVIS_SECRET_TOKEN)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$LockFile = Join-Path $ProjectRoot "storage\runtime\jarvis.pid"
$SettingsFile = Join-Path $ProjectRoot "jarvis_ai\config\settings.yaml"

function Get-ConfigToken {
    if (-not (Test-Path $SettingsFile)) {
        return $null
    }

    $match = Select-String -Path $SettingsFile -Pattern '^\s*security_token:\s*"([^"]+)"' | Select-Object -First 1
    if ($match -and $match.Matches.Count -gt 0) {
        return $match.Matches[0].Groups[1].Value
    }

    return $null
}

if (-not $Token) {
    $Token = Get-ConfigToken
}

Write-Host ""
Write-Host "==============================" -ForegroundColor Cyan
Write-Host "  Jarvis Status Check" -ForegroundColor Cyan
Write-Host "==============================" -ForegroundColor Cyan
Write-Host ""

if (Test-Path $LockFile) {
    $pidVal = (Get-Content $LockFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    $proc = $null

    if ($pidVal) {
        $proc = Get-Process -Id $pidVal -ErrorAction SilentlyContinue
    }

    if ($proc) {
        Write-Host "[OK]   Process     : Running (PID $pidVal)" -ForegroundColor Green
    } else {
        Write-Host "[WARN] Process     : Stale lockfile or missing process (PID $pidVal)" -ForegroundColor Yellow
        Write-Host "       Cleanup     : .\scripts\stop_jarvis.ps1"
    }
} else {
    Write-Host "[INFO] Process     : No lockfile; server is likely stopped" -ForegroundColor Yellow
}

try {
    $ProgressPreference = 'SilentlyContinue'
    $headers = @{}
    if ($Token) {
        $headers["X-Jarvis-Token"] = $Token
    }

    $response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" `
        -Headers $headers `
        -UseBasicParsing `
        -TimeoutSec 3 -ErrorAction Stop
    Write-Host "[OK]   HTTP Health : $($response.StatusCode) OK" -ForegroundColor Green
} catch {
    Write-Host "[FAIL] HTTP Health : Unreachable ($($_.Exception.Message))" -ForegroundColor Red
}

if ($Token) {
    try {
        $readiness = Invoke-RestMethod -Uri "http://127.0.0.1:8000/control/readiness" `
            -Headers @{ "X-Jarvis-Token" = $Token } `
            -TimeoutSec 3 -ErrorAction Stop

        $readinessColor = if ($readiness.overall -eq "ready") { "Green" } else { "Yellow" }
        Write-Host "[INFO] Readiness   : $($readiness.overall.ToUpper())" -ForegroundColor $readinessColor

        if ($readiness.google_integration) {
            $googleColor = if ($readiness.google_integration.status -eq "available") { "Green" } else { "Yellow" }
            Write-Host "[INFO] Google      : $($readiness.google_integration.status)" -ForegroundColor $googleColor
        }
    } catch {
        Write-Host "[WARN] Readiness   : Could not fetch (server may be offline)" -ForegroundColor Yellow
    }
} else {
    Write-Host "[WARN] Readiness   : Skipped (owner token not found in env or config)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==============================" -ForegroundColor Cyan
