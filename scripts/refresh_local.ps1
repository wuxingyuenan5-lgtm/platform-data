param(
    [string]$DataRoot = "D:\自营数据库\hedge-board"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$logRoot = Join-Path $DataRoot "logs"
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
$logPath = Join-Path $logRoot ("refresh-{0}.log" -f (Get-Date -Format "yyyyMMdd-HHmmss"))
$failures = [System.Collections.Generic.List[string]]::new()

function Invoke-PlatformDataCommand {
    param([Parameter(Mandatory)][string]$Command)
    "[$(Get-Date -Format o)] START $Command" | Tee-Object -FilePath $logPath -Append
    & python -m platform_data.cli --data-root $DataRoot $Command 2>&1 |
        Tee-Object -FilePath $logPath -Append
    if ($LASTEXITCODE -ne 0) {
        $failures.Add($Command)
        "[$(Get-Date -Format o)] FAILED $Command" | Tee-Object -FilePath $logPath -Append
    }
}

Push-Location $repoRoot
try {
    Invoke-PlatformDataCommand "refresh-treasury-market-tenors"
    Invoke-PlatformDataCommand "refresh-fred-macro-core"
    Invoke-PlatformDataCommand "refresh-yahoo-macro-market"
    Invoke-PlatformDataCommand "refresh-global-m2"
    Invoke-PlatformDataCommand "refresh-chinabond-market-tenors"
    Invoke-PlatformDataCommand "build-macro-market-detail"
    Invoke-PlatformDataCommand "build-macro-dashboard"
    Invoke-PlatformDataCommand "refresh-cftc-commodity-core"
    if ([string]::IsNullOrWhiteSpace($env:EIA_API_KEY)) {
        "[$(Get-Date -Format o)] SKIP refresh-eia-commodity-core: EIA_API_KEY unavailable" |
            Tee-Object -FilePath $logPath -Append
    } else {
        Invoke-PlatformDataCommand "refresh-eia-commodity-core"
    }
    Invoke-PlatformDataCommand "build-commodity-dashboard"
    Invoke-PlatformDataCommand "refresh-binance-crypto-core"
    Invoke-PlatformDataCommand "build-crypto-dashboard"
    Invoke-PlatformDataCommand "sync-local-database"
} finally {
    Pop-Location
}

if ($failures.Count -gt 0) {
    "Failed commands: $($failures -join ', ')" | Tee-Object -FilePath $logPath -Append
    exit 1
}

"[$(Get-Date -Format o)] COMPLETE" | Tee-Object -FilePath $logPath -Append
