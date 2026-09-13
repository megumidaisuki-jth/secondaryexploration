$python = 'C:\Users\jiate\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$root = 'E:\second'
$diag = 'E:\second\results\diagnostics\confirmation-bounded-scheduler\confirmation-20260831-memory-v1'
$arguments = @(
  'tools\confirmation_bounded_scheduler.py',
  '--session-id', 'confirmation-20260831-memory-v1',
  '--orchestration-revision', 'f0b2f246dccec7bd20b9215870e8971687f9496d',
  '--readiness-authorization-revision', 'f0b2f246dccec7bd20b9215870e8971687f9496d',
  '--python-executable', $python,
  '--resume'
)
$process = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput (Join-Path $diag 'scheduler-next.stdout.log') -RedirectStandardError (Join-Path $diag 'scheduler-next.stderr.log') -PassThru
$process.Id | Set-Content -LiteralPath (Join-Path $diag 'scheduler-detached.pid') -NoNewline
