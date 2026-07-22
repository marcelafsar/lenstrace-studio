# Build the Electron desktop app into a Windows installer with electron-builder.
#
# Phase 5 scaffold — NOT yet verified end-to-end. See docs/packaging-windows.md.
# Run scripts\build_backend.ps1 first and enable extraResources in
# desktop\electron-builder.yml so the backend executable is bundled.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $root 'desktop')

Write-Host 'Installing desktop dependencies...' -ForegroundColor Cyan
npm install

Write-Host 'Building renderer + electron bundles...' -ForegroundColor Cyan
npm run build

Write-Host 'Packaging with electron-builder...' -ForegroundColor Cyan
npm run electron:build

Write-Host 'Done. Installer is in desktop\release\.' -ForegroundColor Green
Write-Host 'NOTE: This build has not been verified end-to-end.' -ForegroundColor Yellow
