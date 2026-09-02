param(
    [string]$DataRoot = "D:\自营数据库\hedge-board",
    [string]$TaskName = "HedgeBoard-LocalData-Refresh"
)

$ErrorActionPreference = "Stop"
$refreshScript = Join-Path $PSScriptRoot "refresh_local.ps1"
if (-not (Test-Path -LiteralPath $refreshScript -PathType Leaf)) {
    throw "Refresh script not found: $refreshScript"
}

$pwsh = (Get-Command pwsh.exe -ErrorAction Stop).Source
$arguments = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$refreshScript`" -DataRoot `"$DataRoot`""
$action = New-ScheduledTaskAction -Execute $pwsh -Argument $arguments -WorkingDirectory (Split-Path -Parent $PSScriptRoot)
$triggers = @(
    New-ScheduledTaskTrigger -Daily -At "00:15"
    New-ScheduledTaskTrigger -Daily -At "06:15"
    New-ScheduledTaskTrigger -Daily -At "12:15"
    New-ScheduledTaskTrigger -Daily -At "18:15"
)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2)
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $triggers -Settings $settings -Principal $principal -Description "Refresh Hedge Board local market data and DuckDB serving mirror." -Force | Out-Null
Get-ScheduledTask -TaskName $TaskName | Select-Object TaskName, State
