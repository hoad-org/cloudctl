# install.ps1 — awsctl installer for Windows PowerShell / pwsh
# Run from the repo root:  .\install.ps1
#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Write-Host "🚀 Starting awsctl installation..." -ForegroundColor Cyan

# ---------------------------------------------------------------------------
# 1. Install the Python package
# ---------------------------------------------------------------------------
Write-Host "📦 Installing package via pip..." -ForegroundColor Cyan
pip install --user .

# Ensure the user Scripts directory is on PATH for this session
$ScriptsDir = python -c "import site, os, sys; print(os.path.join(site.getuserbase(), 'Scripts'))"
if ($ScriptsDir -and ($env:PATH -notlike "*$ScriptsDir*")) {
    $env:PATH = "$env:PATH;$ScriptsDir"
    Write-Host "  Added $ScriptsDir to PATH for this session." -ForegroundColor DarkGray
}

# ---------------------------------------------------------------------------
# 2. Inject the PowerShell function wrapper
# ---------------------------------------------------------------------------
Write-Host "🐚 Installing PowerShell shell integration..." -ForegroundColor Cyan

$result = python -c @"
from awsctl import shell
target = shell.detect_powershell_profile()
ok = shell.inject_powershell_function(target)
print('installed', str(target)) if ok else print('already_present', str(target))
"@

if ($result -like 'installed*') {
    $profilePath = $result -replace '^installed ', ''
    Write-Host "  ✅ Shell integration installed in $profilePath" -ForegroundColor Green
} else {
    $profilePath = $result -replace '^already_present ', ''
    Write-Host "  ℹ️  Shell integration already present in $profilePath" -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# 3. Reload message
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "✨ Installation complete!" -ForegroundColor Green
Write-Host "   Reload your profile:"
Write-Host "     . `$PROFILE" -ForegroundColor White
Write-Host ""
Write-Host "   Then verify:"
Write-Host "     awsctl --version"
Write-Host "     awsctl doctor"
