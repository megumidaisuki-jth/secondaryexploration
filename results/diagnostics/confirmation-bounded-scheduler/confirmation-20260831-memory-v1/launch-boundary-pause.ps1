$diag = 'E:\second\results\diagnostics\confirmation-bounded-scheduler\confirmation-20260831-memory-v1'
$watcher = Join-Path $diag 'pause-after-batch-035.ps1'
$process = Start-Process -FilePath 'powershell.exe' -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $watcher) -WindowStyle Hidden -PassThru
$process.Id | Set-Content -LiteralPath (Join-Path $diag 'boundary-pause-035.pid') -NoNewline
