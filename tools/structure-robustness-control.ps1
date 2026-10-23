param(
    [ValidateSet('start','pause','resume','status')][string]$Action = 'status',
    [ValidateSet('auto','engineering','A')][string]$Stage = 'auto'
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = 'D:\miniconda\python.exe'
if ($Stage -eq 'auto') {
    $Stage = if (Test-Path -LiteralPath (Join-Path $projectRoot 'results\diagnostics\structure-robustness-A-v1\tests.json')) { 'A' } else { 'engineering' }
}
$moduleName = if ($Stage -eq 'A') { 'tools.structure_robustness_A' } else { 'tools.structure_robustness_engineering' }
$outputName = if ($Stage -eq 'A') { 'structure-robustness-A-v1' } else { 'structure-robustness-engineering-v1' }
Push-Location -LiteralPath $projectRoot
try {
    if ($Action -in @('pause', 'status')) {
        & $pythonPath -X utf8 -m $moduleName $Action
        if ($LASTEXITCODE -ne 0) { throw 'Control command failed' }
    } else {
        $outPath = Join-Path $projectRoot "results\supplement\$outputName"
        New-Item -ItemType Directory -Force -Path $outPath | Out-Null
        $stamp = Get-Date -Format 'yyyyMMddTHHmmssfff'
        $command = if ($Action -eq 'start') { 'run' } else { 'resume' }
        $process = Start-Process -FilePath $pythonPath -ArgumentList @('-X','utf8','-m',$moduleName,$command) -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $outPath "$stamp.stdout.log") -RedirectStandardError (Join-Path $outPath "$stamp.stderr.log")
        # Only affects this experiment, never another task.
        try { $process.PriorityClass = 'BelowNormal' } catch { Write-Warning $_ }
        Write-Output "Stage=$Stage. Launch requested. PID=$($process.Id). Use status to verify the runner."
    }
} finally { Pop-Location }
