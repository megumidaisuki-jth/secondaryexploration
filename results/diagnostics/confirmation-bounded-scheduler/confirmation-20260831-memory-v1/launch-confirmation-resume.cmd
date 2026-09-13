@echo off
cd /d E:\second
"C:\Users\jiate\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" tools\confirmation_bounded_scheduler.py --session-id confirmation-20260831-memory-v1 --orchestration-revision f0b2f246dccec7bd20b9215870e8971687f9496d --readiness-authorization-revision f0b2f246dccec7bd20b9215870e8971687f9496d --python-executable C:\Users\jiate\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe --resume --recover-interrupted --recover-global-lease 1>> E:\second\results\diagnostics\confirmation-bounded-scheduler\confirmation-20260831-memory-v1\scheduler-task.stdout.log 2>> E:\second\results\diagnostics\confirmation-bounded-scheduler\confirmation-20260831-memory-v1\scheduler-task.stderr.log
exit /b %ERRORLEVEL%
