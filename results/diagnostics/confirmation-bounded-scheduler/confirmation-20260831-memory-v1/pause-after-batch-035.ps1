$root = 'E:\second'
$final = Join-Path $root 'results\diagnostics\confirmation-bounded-scheduler\confirmation-20260831-memory-v1\batch-035.final.json'
$record = Join-Path $root 'results\diagnostics\confirmation-bounded-scheduler\confirmation-20260831-memory-v1\boundary-pause-035.json'
while (-not (Test-Path -LiteralPath $final)) {
  Start-Sleep -Seconds 1
}
$schedulers = @(Get-CimInstance Win32_Process | Where-Object {
  $_.Name -eq 'python.exe' -and $_.CommandLine -match 'confirmation_bounded_scheduler\.py'
})
foreach ($scheduler in $schedulers) {
  $children = @(Get-CimInstance Win32_Process | Where-Object {
    $_.ParentProcessId -eq $scheduler.ProcessId -and $_.Name -eq 'python.exe' -and $_.CommandLine -match 'synthetic-confirmation-v1\.json'
  })
  foreach ($child in $children) {
    Stop-Process -Id $child.ProcessId -Force -ErrorAction SilentlyContinue
  }
  Stop-Process -Id $scheduler.ProcessId -Force -ErrorAction SilentlyContinue
}
[pscustomobject]@{ status = 'paused-after-batch-035-final-witness'; paused_at_utc = (Get-Date).ToUniversalTime().ToString('o') } | ConvertTo-Json -Compress | Set-Content -LiteralPath $record -NoNewline
