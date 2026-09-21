# ==============================================================================
# deploy.ps1 — Auto-detect hardware, launch the matching compose profile.
#
# PowerShell-native equivalent of deploy.sh, for exactly the situation you're
# in: Docker Desktop on Windows, no working `bash` reachable via `wsl bash ...`
# (that command runs Docker Desktop's own minimal internal WSL distro by
# default, which doesn't ship bash — this script sidesteps that entirely by
# not touching WSL at all).
#
# Picks, in order:
#   1. gpu  — only if Docker can ACTUALLY attach an NVIDIA GPU right now
#             (runs a real `docker run --gpus all` test, not just "is
#             nvidia-smi.exe on PATH" — those are different: the driver can
#             be installed and working for other apps while Docker Desktop's
#             GPU passthrough / WSL2 GPU support isn't set up, which is a
#             very common way this silently ends up broken).
#   2. cpu  — fallback, always works. (Jetson isn't a Windows target, so
#             this script doesn't check for it — use deploy.sh on-device.)
#
# Usage (from PowerShell, in apps/slm-server or anywhere — it cd's itself):
#   .\scripts\deploy.ps1                # detect + up -d (detached)
#   .\scripts\deploy.ps1 -Logs          # detect + up (attached, streaming logs)
#   .\scripts\deploy.ps1 -ForceCpu
#   .\scripts\deploy.ps1 -ForceGpu
#
# If PowerShell blocks running local scripts, run once per session:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
# ==============================================================================
param(
    [switch]$Logs,
    [switch]$ForceCpu,
    [switch]$ForceGpu
)

$ErrorActionPreference = 'Stop'

function Write-Info    ($msg) { Write-Host "[i] $msg" -ForegroundColor Cyan }
function Write-Ok      ($msg) { Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Warn2   ($msg) { Write-Host "[!] $msg" -ForegroundColor Yellow }
function Write-Err2    ($msg) { Write-Host "[X] $msg" -ForegroundColor Red }

# cd to apps/slm-server (this script lives in apps/slm-server/scripts/)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $ScriptDir "..")

Write-Host "======================================================" -ForegroundColor Blue
Write-Host "   Ssense SLM Server - Auto-Detecting Deploy Target    " -ForegroundColor Blue
Write-Host "======================================================`n" -ForegroundColor Blue

# ------------------------------------------------------------------------------
# Detection
# ------------------------------------------------------------------------------
function Test-NvidiaSmiPresent {
    $null = Get-Command nvidia-smi -ErrorAction SilentlyContinue
    return $?
}

function Test-DockerCanUseGpu {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { return $false }
    try {
        docker run --rm --gpus all alpine:3.20 sh -c 'exit 0' *>$null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

$Profile_ = $null
$Reason   = $null

if ($ForceCpu) {
    $Profile_ = "cpu"; $Reason = "forced via -ForceCpu"
} elseif ($ForceGpu) {
    $Profile_ = "gpu"; $Reason = "forced via -ForceGpu"
} elseif (Test-DockerCanUseGpu) {
    $Profile_ = "gpu"
    $gpuName = (nvidia-smi --query-gpu=name --format=csv,noheader 2>$null | Select-Object -First 1)
    $Reason = "Docker can attach an NVIDIA GPU ($gpuName)"
} else {
    $Profile_ = "cpu"
    if (Test-NvidiaSmiPresent) {
        $Reason = "NVIDIA driver found, but Docker cannot use it - is Docker Desktop's GPU support enabled (Settings > Resources > WSL Integration / GPU)? Falling back to CPU"
    } else {
        $Reason = "no usable GPU detected"
    }
}

Write-Ok   "Selected profile: $Profile_"
Write-Info "Reason: $Reason`n"

if ($Profile_ -eq "cpu" -and -not $ForceCpu -and (Test-NvidiaSmiPresent)) {
    Write-Warn2 "You have an NVIDIA GPU but Docker can't reach it - CPU mode will work but be much slower."
    Write-Warn2 "Check Docker Desktop > Settings > Resources > GPU (or WSL Integration), and that you're on a recent Docker Desktop + driver version."
    Write-Warn2 "Once fixed, re-run this script, or pass -ForceGpu once you've confirmed it works.`n"
}

if (-not (Test-Path ".env")) {
    Write-Warn2 ".env not found - run.sh/README normally generates one with a fresh SSENSE_SERVER_KEY."
    Write-Warn2 "Continuing with docker-compose.yml's built-in defaults; set up .env before real deployment.`n"
}

# ------------------------------------------------------------------------------
# Launch
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# Launch
# ------------------------------------------------------------------------------
# NOTE: deliberately NOT using array-splatting (@detachArg) here. Splatting an
# array to a native executable (as opposed to a PowerShell cmdlet/function) is
# unreliable in Windows PowerShell — it can fragment "-d" into separate "-"
# and "d" tokens, which is exactly what produced the "no such service: -"
# error. Two explicit branches avoid the issue entirely.
if ($Logs) {
    Write-Info "Running: docker compose --profile $Profile_ up --build`n"
    docker compose --profile $Profile_ up --build
} else {
    Write-Info "Running: docker compose --profile $Profile_ up --build -d`n"
    docker compose --profile $Profile_ up --build -d
}

if (-not $Logs) {
    Write-Host ""
    Write-Ok "Started in background. Follow logs with:"
    Write-Host "    docker compose logs -f slm-server-$Profile_"
    Write-Ok "Check health with:"
    Write-Host "    docker compose ps"
}
