# =====================================================================
# nightly_sweep.ps1 — collector lane (§6.4). Folds tonight's lane outputs
# and the latest work-packet result files + log tails into a single
# summary.json. The 07:06 Claude session reads this FIRST so each morning
# starts from measured truth.
# =====================================================================
. "$PSScriptRoot\automation_config.ps1"
$nightly = Get-NightlyDir

function Read-Json($path) {
    if (Test-Path $path) { try { return Get-Content $path -Raw | ConvertFrom-Json } catch { return $null } }
    return $null
}

$tests  = Read-Json (Join-Path $nightly "tests.json")
$render = Read-Json (Join-Path $nightly "render.json")

# Latest per-packet result files (wp_*_result.json) for the burndown view.
$wp = @{}
Get-ChildItem $ReportsDir -Filter "wp_*_result.json" -ErrorAction SilentlyContinue |
    Sort-Object Name | ForEach-Object {
        $j = Read-Json $_.FullName
        if ($j) { $wp[$_.BaseName] = @{ auto_result = $j.auto_result; passed = $j.gates_passed; total = $j.gates_total } }
    }

# Tail the newest UE log if present.
$logTail = @()
$logDir = Join-Path $ProjectRoot "NaviSense_UE5\Saved\Logs"
$log = Get-ChildItem $logDir -Filter *.log -ErrorAction SilentlyContinue |
       Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($log) { $logTail = Get-Content $log.FullName -Tail 40 }

$testsGreen  = if ($tests)  { $tests.green }  else { $null }
$renderGreen = if ($render) { $render.green } else { $null }
$overall = (($testsGreen -ne $false) -and ($renderGreen -ne $false))

$summary = [ordered]@{
    date          = (Get-Date -Format "yyyy-MM-dd")
    timestamp     = (Get-Date).ToString("o")
    overall_green = [bool]$overall
    tests         = $tests
    render        = $render
    work_packets  = $wp
    ue_log        = $log.Name
    ue_log_tail   = $logTail
}
$out = Join-Path $nightly "summary.json"
$summary | ConvertTo-Json -Depth 8 | Set-Content $out
Write-Host "[nightly_sweep] overall_green=$overall -> $out"
