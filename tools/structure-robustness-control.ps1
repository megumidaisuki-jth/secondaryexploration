param([ValidateSet('start','pause','resume','status')][string]$Action = 'status')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = 'D:\miniconda\python.exe'
Push-Location -LiteralPath $projectRoot
try {
    if ($Action -in @('pause', 'status')) {
        & $pythonPath -X utf8 -m tools.structure_robustness_engineering $Action
        if ($LASTEXITCODE -ne 0) { throw 'Control command failed' }
    } else {
        $outPath = Join-Path $projectRoot 'results\supplement\structure-robustness-engineering-v1'
        New-Item -ItemType Directory -Force -Path $outPath | Out-Null
        $stamp = Get-Date -Format 'yyyyMMddTHHmmssfff'
        $command = if ($Action -eq 'start') { 'run' } else { 'resume' }
        $process = Start-Process -FilePath $pythonPath -ArgumentList @('-X','utf8','-m','tools.structure_robustness_engineering',$command) -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $outPath "$stamp.stdout.log") -RedirectStandardError (Join-Path $outPath "$stamp.stderr.log")
        # BelowNormal only affects this new pilot, never another experiment.
        try { $process.PriorityClass = 'BelowNormal' } catch { Write-Warning $_ }
        Write-Output "Launch requested. PID=$($process.Id). Use status to verify the runner."
    }
} finally { Pop-Location }
