# =====================================================================
# nightly.ps1 — master orchestrator (runs at 02:00 via Task Scheduler).
# Order: tests -> render -> sweep. Each lane writes its own JSON; sweep folds
# them into summary.json. Always runs sweep even if a lane fails, so the
# morning session always has a summary to read.
# =====================================================================
. "$PSScriptRoot\automation_config.ps1"

Write-Section "NaviSense nightly  $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
$nightly = Get-NightlyDir
Start-Transcript -Path (Join-Path $nightly "nightly_console.log") -Force | Out-Null

try {
    & "$PSScriptRoot\nightly_tests.ps1"
    $testsExit = $LASTEXITCODE
    & "$PSScriptRoot\nightly_render.ps1"
    $renderExit = $LASTEXITCODE
}
finally {
    & "$PSScriptRoot\nightly_sweep.ps1"
    Stop-Transcript | Out-Null
}

Write-Host "`n[nightly] tests exit=$testsExit render exit=$renderExit"
Write-Host "[nightly] summary: $(Join-Path $nightly 'summary.json')"
