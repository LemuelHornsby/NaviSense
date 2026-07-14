# =====================================================================
# nightly_tests.ps1 — code verification lane (WP-5, F7).
# Runs the Python suite (pytest + harness selftest + bridge re-accept verify)
# and the UE C++ Automation tests (NaviSense.*), then writes tests.json into
# tonight's nightly folder. Exit code 0 = all green.
# =====================================================================
. "$PSScriptRoot\automation_config.ps1"
$nightly = Get-NightlyDir
$results = [ordered]@{}

Write-Section "Python: pytest (plant + wire contract)"
& $Python -m pytest "$HarnessDir\tests" -q
$results["pytest"] = ($LASTEXITCODE -eq 0)

Write-Section "Python: bridge re-accept verifies"
& $Python "$HarnessDir\verify_root_reaccept.py"
$results["root_reaccept"] = ($LASTEXITCODE -eq 0)
& $Python "$ProjectRoot\Development\work_packets\WP_20260614\verify_20260614.py"
$results["wp3_reaccept"] = ($LASTEXITCODE -eq 0)
& $Python "$ProjectRoot\Development\work_packets\WP_20260615\verify_20260615.py"
$results["wp4_clock"] = ($LASTEXITCODE -eq 0)

Write-Section "UE: Automation RunTests NaviSense"
if (Test-Path $EditorCmd) {
    $ueReport = Join-Path $nightly "ue_tests"
    & $EditorCmd "$UProject" `
        -ExecCmds="Automation RunTests NaviSense; Quit" `
        -unattended -nullrhi -nosplash -nopause -log `
        -ReportExportPath="$ueReport"
    # UE writes index.json in the report dir; success iff it has no failures.
    $idx = Join-Path $ueReport "index.json"
    if (Test-Path $idx) {
        $j = Get-Content $idx -Raw | ConvertFrom-Json
        $failed = @($j.tests | Where-Object { $_.state -ne "Success" }).Count
        $results["ue_automation"] = ($failed -eq 0)
    } else {
        $results["ue_automation"] = $false
    }
} else {
    Write-Warning "UnrealEditor-Cmd not found at $EditorCmd — set `$env:UE_ROOT. Skipping UE tests."
    $results["ue_automation"] = $null   # null = skipped (not a hard fail offline)
}

$allGreen = -not ($results.Values | Where-Object { $_ -eq $false })
$payload = [ordered]@{
    lane        = "tests"
    timestamp   = (Get-Date).ToString("o")
    results     = $results
    green       = [bool]$allGreen
}
$payload | ConvertTo-Json -Depth 6 | Set-Content (Join-Path $nightly "tests.json")
Write-Host "`n[nightly_tests] green=$allGreen -> $(Join-Path $nightly 'tests.json')"
if ($allGreen) { exit 0 } else { exit 1 }
