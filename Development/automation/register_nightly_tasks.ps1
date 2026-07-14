# =====================================================================
# register_nightly_tasks.ps1 — install the 02:00 nightly into Windows Task
# Scheduler. Run ONCE from an elevated PowerShell:
#     powershell -ExecutionPolicy Bypass -File .\register_nightly_tasks.ps1
# Remove with:  Unregister-ScheduledTask -TaskName "NaviSense Nightly" -Confirm:$false
# =====================================================================
. "$PSScriptRoot\automation_config.ps1"

$taskName = "NaviSense Nightly"
$script   = Join-Path $PSScriptRoot "nightly.ps1"

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`""
$trigger = New-ScheduledTaskTrigger -Daily -At 2:00am
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

# Run as the current user, only when logged on (UE needs a desktop session for
# the render lane; -nullrhi test lane would run headless but we keep one task).
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Force `
    -Description "NaviSense nightly: pytest + UE Automation + beauty render + summary sweep (WP-5)."

Write-Host "Registered '$taskName' for 02:00 daily."
Write-Host "Test it now with:  Start-ScheduledTask -TaskName `"$taskName`""
