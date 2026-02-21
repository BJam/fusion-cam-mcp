#Requires -Version 5.1
<#
.SYNOPSIS
    Downloads the latest fusion-cam-mcp binary for Windows and runs --install.
.EXAMPLE
    irm https://raw.githubusercontent.com/BJam/fusion-cam-mcp/main/install.ps1 | iex
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Repo       = "BJam/fusion-cam-mcp"
$Asset      = "fusion-cam-mcp-windows-x64.exe"
$InstallDir = Join-Path $env:LOCALAPPDATA "fusion-cam-mcp"
$Binary     = Join-Path $InstallDir "fusion-cam-mcp.exe"

function Write-Info { param([string]$Msg) Write-Host "  ✓ $Msg" -ForegroundColor Green }
function Write-Err  { param([string]$Msg) Write-Host "  ✗ $Msg" -ForegroundColor Red }

function Main {
    Write-Host ""
    Write-Host "  ╔══════════════════════════════════════════════╗"
    Write-Host "  ║  Fusion 360 CAM MCP — Download & Install     ║"
    Write-Host "  ╚══════════════════════════════════════════════╝"
    Write-Host ""

    Write-Info "Platform: $Asset"

    $Url = "https://github.com/$Repo/releases/latest/download/$Asset"

    if (-not (Test-Path $InstallDir)) {
        New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    }

    Write-Host ""
    Write-Host "── Downloading latest release ──"

    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $wc = New-Object System.Net.WebClient
        $wc.DownloadFile($Url, $Binary)
    } catch {
        Write-Err "Download failed: $_"
        Write-Host "  URL: $Url"
        exit 1
    }

    Write-Info "Downloaded to $Binary"

    Write-Host ""
    Write-Host "── Running installer ──"
    & $Binary --install
}

Main
