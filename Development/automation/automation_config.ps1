# =====================================================================
# automation_config.ps1 — shared paths for the NaviSense nightly pipeline.
# EDIT $UeRoot ONCE to point at your installed Unreal Engine 5.7, then the
# other scripts work unchanged. Dot-source this from the other scripts:
#     . "$PSScriptRoot\automation_config.ps1"
# =====================================================================

# --- EDIT ME: your UE 5.7 install root (the folder that contains 'Engine\') ---
$UeRoot = $env:UE_ROOT
if (-not $UeRoot) {
    # Common Epic Launcher default; change if yours differs.
    $UeRoot = "C:\Program Files\Epic Games\UE_5.7"
}

# --- Derived paths (do not normally need editing) ---------------------
$ProjectRoot   = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)   # ...\NaviSense Simulator with Unreal Engine
$WorkspaceRoot = Split-Path -Parent $ProjectRoot                          # ...\NAVISENSE
$UProject      = Join-Path $ProjectRoot "NaviSense_UE5\NaviSense_UE5.uproject"
$ReportsDir    = Join-Path $ProjectRoot "NaviSense_UE5\Saved\NaviSense_Reports"
$NightlyRoot   = Join-Path $ReportsDir  "nightly"
$EditorCmd     = Join-Path $UeRoot      "Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
$HarnessDir    = Join-Path $ProjectRoot "Development\bridge_harness"
$AutomationDir = $PSScriptRoot

# Python: prefer the repo venv if present, else 'python' on PATH.
$VenvPy = Join-Path $WorkspaceRoot ".venv\Scripts\python.exe"
$Python = if (Test-Path $VenvPy) { $VenvPy } else { "python" }

function Get-NightlyDir {
    $stamp = Get-Date -Format "yyyy-MM-dd"
    $dir = Join-Path $NightlyRoot $stamp
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    return $dir
}

function Write-Section($msg) { Write-Host "`n==== $msg ====" -ForegroundColor Cyan }
