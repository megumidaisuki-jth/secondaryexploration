# Formal batch 045 interruption recovery

This is a result-blind operational recovery record. No scientific endpoint,
interval, gate, point estimate, or aggregate was read.

## Interrupted state and independent audit

The frozen Formal session `formal-20260811-memory-v1` had 228 canonical block
JSON files. Scheduler PID `20176`, its parent, and batch-045 worker PIDs `240`,
`1484`, `5584`, `10776`, `3516`, and `9844` were absent. The global lease still
named PID `20176`, and was therefore stale.

An independent result-blind audit validated the frozen session and source
hashes, accepted exactly indices `0..227`, and verified that batch 045 remains
the unique incomplete batch for indices `228..233`. No pending artifact,
temporary file, foreign entry, or new worker stderr was present. The six locks
under `blocks/.locks` were exactly the six planned pending block keys and named
only the six absent recorded worker PIDs. The audit approved deletion of only
those locks.

Immediately before deletion, the six lock filenames, owner-PID absence,
artifact absence, and SHA-256 values were rechecked. Only the approved locks
were removed. Batch 045 contributes zero accepted indices; workers `228..233`
remain pending until new frozen singleton children exit successfully.

The frozen scheduler restarted with `--resume --recover-interrupted
--recover-global-lease`. It wrote `batch-045.recovery.json`, acquired a fresh
lease, and launched batch 046 for indices `228..233`. Scheduler PID `12024` is
the live parent of worker PIDs `19616`, `8532`, `17060`, `11712`, `10780`, and
`21388`; six expected locks are present and scheduler stderr is empty.
