#Requires -Version 5.1
<#
.SYNOPSIS
    Developer install: venv, pip install -e ., fusion-cam --install (Fusion bridge add-in).
.EXAMPLE
    cd fusion-cam-mcp; .\install.ps1
.EXAMPLE
    irm https://raw.githubusercontent.com/BJam/fusion-cam-mcp/main/install.ps1 | iex
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoUrl = if ($env:FUSION_CAM_REPO_URL) { $env:FUSION_CAM_REPO_URL } else { "https://github.com/BJam/fusion-cam-mcp.git" }
$CloneDir = $env:FUSION_CAM_CLONE_DIR

function Write-Info { param([string]$Msg) Write-Host "  ✓ $Msg" -ForegroundColor Green }
function Write-Err  { param([string]$Msg) Write-Host "  ✗ $Msg" -ForegroundColor Red }

function Test-RepoRoot {
    return (Test-Path -LiteralPath "pyproject.toml") -and (Select-String -Path "pyproject.toml" -Pattern "fusion-cam-mcp" -Quiet)
}

function Ensure-Repo {
    if (Test-RepoRoot) { return }
    if (-not $CloneDir) {
        Write-Err "Not in the fusion-cam-mcp repo root. Clone first, or set FUSION_CAM_CLONE_DIR:"
        Write-Err "  git clone $RepoUrl; cd fusion-cam-mcp; .\install.ps1"
        exit 1
    }
    if (-not (Test-Path -LiteralPath $CloneDir)) {
        Write-Info "Cloning into $CloneDir"
        git clone --depth 1 $RepoUrl $CloneDir
    }
    Set-Location $CloneDir
}

function Main {
    Write-Host ""
    Write-Host "  ╔══════════════════════════════════════════════╗"
    Write-Host "  ║  Fusion 360 CAM CLI — developer install      ║"
    Write-Host "  ╚══════════════════════════════════════════════╝"
    Write-Host ""

    Ensure-Repo

    $py = Get-Command python3 -ErrorAction SilentlyContinue
    if (-not $py) {
        Write-Err "python3 not found. Install Python 3.10+ and retry."
        exit 1
    }

    if (-not (Test-Path -LiteralPath ".venv")) {
        Write-Info "Creating .venv"
        & python3 -m venv .venv
    }

    $venvPy = Join-Path (Get-Location) ".venv\Scripts\python.exe"
    $pip = Join-Path (Get-Location) ".venv\Scripts\pip.exe"
    $fusionCam = Join-Path (Get-Location) ".venv\Scripts\fusion-cam.exe"
    & $venvPy -m pip install -q --upgrade pip
    Write-Host ""
    Write-Host "── pip install -e . ──"
    & $pip install -e .

    Write-Host ""
    Write-Host "── fusion-cam --install (Fusion bridge add-in) ──"
    & $fusionCam --install

    Write-Host ""
    Write-Info "Done."
    Write-Host ""
    Write-Host "Next steps:"
    Write-Host "  1. Open Fusion 360 → Scripts and Add-ins → run add-in: fusion-bridge"
    Write-Host "  2. Use the CLI:  .\.venv\Scripts\Activate.ps1; fusion-cam ping"
    Write-Host "  3. Cursor: keep .cursor/rules/fusion-cam-cli.mdc for agent guidance"
    Write-Host ""
}

Main
