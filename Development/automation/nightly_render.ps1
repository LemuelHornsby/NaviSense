# =====================================================================
# nightly_render.ps1 — visual-regression lane (WP-5 skeleton, F7/§6.2).
# Renders one beauty frame of NaviSense_Monaco to tonight's nightly folder.
# Uses a HighResShot now; swap to Movie Render Queue in WP-20 (D7) once the
# MRQ_Nightly preset exists. Gate: one PNG lands under Saved/.../nightly/<date>/.
# =====================================================================
. "$PSScriptRoot\automation_config.ps1"
$nightly = Get-NightlyDir
$shotName = "beauty_monaco.png"

if (-not (Test-Path $EditorCmd)) {
    Write-Warning "UnrealEditor-Cmd not found at $EditorCmd — set `$env:UE_ROOT. Skipping render."
    @{ lane = "render"; green = $null; reason = "no engine" } |
        ConvertTo-Json | Set-Content (Join-Path $nightly "render.json")
    exit 0
}

Write-Section "UE: HighResShot of NaviSense_Monaco"
# -game loads the map; the console command fires once the world is up. The shot
# lands in Saved\Screenshots\WindowsEditor — we then move it into the nightly dir.
& $EditorCmd "$UProject" "NaviSense_Monaco" -game `
    -ExecCmds="HighResShot 1920x1080; Quit" `
    -windowed -resx=1920 -resy=1080 -nosplash -nopause -log -unattended

$shotDir = Join-Path $ProjectRoot "NaviSense_UE5\Saved\Screenshots\WindowsEditor"
$latest = Get-ChildItem $shotDir -Filter *.png -ErrorAction SilentlyContinue |
          Sort-Object LastWriteTime -Descending | Select-Object -First 1

$ok = $false
if ($latest) {
    Copy-Item $latest.FullName (Join-Path $nightly $shotName) -Force
    $ok = $true
}
@{ lane = "render"; green = $ok; file = $shotName; timestamp = (Get-Date).ToString("o") } |
    ConvertTo-Json | Set-Content (Join-Path $nightly "render.json")
Write-Host "[nightly_render] png=$ok -> $(Join-Path $nightly $shotName)"
if ($ok) { exit 0 } else { exit 1 }
