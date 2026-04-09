# uninstall.ps1 — awsctl clean uninstaller for Windows PowerShell / pwsh
# Run from the repo root:  .\uninstall.ps1
#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Write-Host "🗑️  Starting awsctl uninstallation..." -ForegroundColor Cyan

# ---------------------------------------------------------------------------
# 1. Remove PowerShell wrapper from $PROFILE
# ---------------------------------------------------------------------------
Write-Host "🧹 Removing shell integration..." -ForegroundColor Cyan

$result = python -c @"
from awsctl import shell
ps_profile = shell.detect_powershell_profile()
ok = shell.remove_powershell_function(ps_profile)
print('removed', str(ps_profile)) if ok else print('not_found', str(ps_profile))
"@ 2>$null

if ($result -like 'removed*') {
    $profilePath = $result -replace '^removed ', ''
    Write-Host "  ✓ Removed PowerShell integration from $profilePath" -ForegroundColor Green
} else {
    Write-Host "  ℹ️  No PowerShell integration found — nothing to remove" -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# 2. Uninstall the Python package
# ---------------------------------------------------------------------------
Write-Host "📦 Uninstalling package..." -ForegroundColor Cyan
pip uninstall -y awsctl 2>$null

# ---------------------------------------------------------------------------
# 3. Remove local state
# ---------------------------------------------------------------------------
Write-Host "🗂️  Removing local state..." -ForegroundColor Cyan

$awsctlDir = Join-Path $env:USERPROFILE ".awsctl"
if (Test-Path $awsctlDir) {
    Remove-Item -Recurse -Force $awsctlDir
    Write-Host "  ✓ Removed $awsctlDir" -ForegroundColor Green
}

$ctxFile = Join-Path $env:APPDATA "awsctl\current_context.json"
if (Test-Path $ctxFile) {
    Remove-Item -Force $ctxFile
}

Write-Host ""
Write-Host "✅ Uninstallation complete. Please restart your PowerShell session." -ForegroundColor Green
