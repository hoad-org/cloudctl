# install.ps1 — awsctl installer for Windows PowerShell / pwsh
# Run from the repo root:  .\install.ps1
#
# Requires GITHUB_TOKEN (PAT with read:contents or repo scope) to download
# from the private repository. Falls back to a local source install if unset.
#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$GithubOrg  = "BT-IT-Infrastructure-CloudOps"
$GithubRepo = "aws-terraform-infra-cloudops-awsctl"
$ApiBase    = "https://api.github.com/repos/$GithubOrg/$GithubRepo"

Write-Host "🚀 Starting awsctl installation..." -ForegroundColor Cyan

# ---------------------------------------------------------------------------
# 0. Python version guard — require 3.12+
# ---------------------------------------------------------------------------
$PythonBin = $null
foreach ($candidate in @("python", "python3")) {
    try {
        $ver = & $candidate -c "import sys; v=sys.version_info; print(f'{v.major}.{v.minor}')" 2>$null
        if ($ver) {
            $parts = $ver.Split('.')
            $major = [int]$parts[0]; $minor = [int]$parts[1]
            if ($major -gt 3 -or ($major -eq 3 -and $minor -ge 12)) {
                $PythonBin = $candidate
                Write-Host "  Using: $candidate $ver" -ForegroundColor DarkGray
                break
            }
        }
    } catch {}
}
if (-not $PythonBin) {
    Write-Host "❌ awsctl requires Python 3.12 or newer." -ForegroundColor Red
    $detected = try { & python --version 2>&1 } catch { "not found" }
    Write-Host "   Detected: $detected" -ForegroundColor Red
    Write-Host ""
    Write-Host "   Install Python 3.12+ from https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "   or via winget:  winget install Python.Python.3.12" -ForegroundColor Yellow
    exit 1
}
$PipCmd = "$PythonBin -m pip"

# ---------------------------------------------------------------------------
# 1. Install the Python package
# ---------------------------------------------------------------------------
Write-Host "📦 Installing package..." -ForegroundColor Cyan

if ($env:GITHUB_TOKEN) {
    Write-Host "  Fetching latest release from GitHub..." -ForegroundColor DarkGray

    $Headers = @{
        Authorization = "Bearer $($env:GITHUB_TOKEN)"
        Accept        = "application/vnd.github.v3+json"
    }
    $Release = Invoke-RestMethod -Uri "$ApiBase/releases/latest" -Headers $Headers
    $Tag     = $Release.tag_name
    Write-Host "  Latest release: $Tag" -ForegroundColor DarkGray

    $WheelAsset = $Release.assets | Where-Object { $_.name -like "*.whl" } | Select-Object -First 1
    if (-not $WheelAsset) {
        Write-Error "No .whl asset found in release $Tag"
    }

    $TmpWhl = [System.IO.Path]::GetTempFileName() -replace '\.tmp$', '.whl'
    Write-Host "  Downloading wheel..." -ForegroundColor DarkGray

    $DownloadHeaders = @{
        Authorization = "Bearer $($env:GITHUB_TOKEN)"
        Accept        = "application/octet-stream"
    }
    Invoke-WebRequest -Uri $WheelAsset.url -Headers $DownloadHeaders -OutFile $TmpWhl

    Write-Host "  Installing from wheel (dependencies from PyPI)..." -ForegroundColor DarkGray
    Invoke-Expression "$PipCmd install --user $TmpWhl --extra-index-url https://pypi.org/simple/"
    Remove-Item -Force $TmpWhl -ErrorAction SilentlyContinue
} else {
    Write-Host "  ⚠️  GITHUB_TOKEN not set — installing from local source." -ForegroundColor Yellow
    Write-Host "  For the latest release: `$env:GITHUB_TOKEN = '<your-PAT>' and re-run." -ForegroundColor Yellow
    Invoke-Expression "$PipCmd install --user . --extra-index-url https://pypi.org/simple/"
}

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
Write-Host ""
Write-Host "   To upgrade later:  awsctl upgrade   (requires GITHUB_TOKEN)" -ForegroundColor White
