# install.ps1 — set up the dedicated crawl4ai venv (Windows PowerShell).
#
# Creates crawl4ai\.venv on Python 3.12, installs crawl4ai, and downloads the
# Playwright/Chromium browser. Isolated from BDOS's own .venv.
#
# Usage:  powershell -ExecutionPolicy Bypass -File crawl4ai\install.ps1

$ErrorActionPreference = "Stop"

$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Venv = Join-Path $Here ".venv"
$PyVer = "3.12"

Write-Host "[crawl4ai] Target venv: $Venv"

$uv = Get-Command uv -ErrorAction SilentlyContinue
if ($uv) {
    Write-Host "[crawl4ai] Creating venv with uv (Python $PyVer)..."
    uv venv --python $PyVer "$Venv"
    Write-Host "[crawl4ai] Installing crawl4ai..."
    uv pip install --python "$Venv\Scripts\python.exe" -U crawl4ai
} else {
    Write-Host "[crawl4ai] uv not found - falling back to py -m venv"
    py -3.12 -m venv "$Venv"
    & "$Venv\Scripts\python.exe" -m pip install -U pip
    & "$Venv\Scripts\python.exe" -m pip install -U crawl4ai
}

Write-Host "[crawl4ai] Downloading browser (Playwright/Chromium)..."
$setup = Join-Path $Venv "Scripts\crawl4ai-setup.exe"
if (Test-Path $setup) {
    & $setup
} else {
    & "$Venv\Scripts\python.exe" -m playwright install chromium
}

Write-Host "[crawl4ai] Smoke test..."
& "$Venv\Scripts\crwl.exe" --help | Out-Null
Write-Host "[crawl4ai] Installed successfully."
