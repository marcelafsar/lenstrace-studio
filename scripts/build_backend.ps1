# Build the Python backend into a standalone Windows executable with PyInstaller.
#
# Phase 5 scaffold — NOT yet verified end-to-end. See docs/packaging-windows.md.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (Test-Path (Join-Path $root '.venv\Scripts\Activate.ps1')) {
    . (Join-Path $root '.venv\Scripts\Activate.ps1')
}

Write-Host 'Building backend executable with PyInstaller...' -ForegroundColor Cyan

# --collect-all ensures data files for tzdata/PIL/piexif are bundled.
pyinstaller `
    --name lenstrace-backend `
    --onefile `
    --distpath backend_dist `
    --collect-all tzdata `
    --collect-submodules uvicorn `
    --add-data "core/presets/iphone_presets.json;core/presets" `
    backend/main.py

Write-Host 'Done. Executable is in backend_dist\.' -ForegroundColor Green
Write-Host 'NOTE: This build has not been verified end-to-end.' -ForegroundColor Yellow
