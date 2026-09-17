$ErrorActionPreference = 'Stop'
$python = 'C:\Users\jiate\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$root = 'E:\second'
$diag = Join-Path $root 'results\diagnostics\post-confirmation\20260917-v1'
New-Item -ItemType Directory -Path $diag -Force | Out-Null
$attempt = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffffffZ')
$child = Start-Process -FilePath $python -ArgumentList @('tools\post_confirmation_pipeline.py') -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput (Join-Path $diag "supervisor-$attempt.stdout.log") -RedirectStandardError (Join-Path $diag "supervisor-$attempt.stderr.log") -PassThru
$child.WaitForExit()
exit $child.ExitCode
