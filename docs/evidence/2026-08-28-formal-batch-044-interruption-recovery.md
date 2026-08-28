# Formal batch 044 interruption recovery

This is a result-blind operational recovery record. No scientific endpoint,
interval, gate, point estimate, or aggregate was read.

## Interrupted state

At `2026-08-28T14:11:18+08:00`, the frozen Formal session
`formal-20260811-memory-v1` had 228 canonical block JSON files. Scheduler PID
`7380` and all batch-044 worker PIDs (`20288`, `19764`, `19628`, `9880`,
`7668`, and `22704`) were absent. The reason for their termination was not
inferred from process absence alone. The global lease still named scheduler PID
`7380`.

The independent result-blind audit validated the frozen execution,
orchestration, and analysis revisions and the session. Strict replay accepted
exactly indices `0..227` and identified `batch-044.launch.json` as the unique
incomplete launch. It attested that batch 044 exactly covers indices `228..233`
and that its started witness exists, while no final or recovery witness exists.
No batch-044 artifacts were written. No runner was live; and no temporary,
foreign, or extra entries existed. All six batch-044 stderr files existed and
were zero bytes.

## Independent audit and recovery

The independent audit then corrected the lock-path check to
`blocks/.locks`. It approved deletion of exactly the six stale batch-044 locks
only: each was on the planned-key whitelist, named an absent batch-044 worker
PID, had no corresponding artifact, and matched the independently attested
SHA-256 registry. No other lock existed. Immediately before deletion, the six
filenames, hashes, owner-PID absence, and artifact absence were rechecked;
only those six lock files were removed.

Recovery may now recover the stale global lease through the frozen scheduler's
`--recover-global-lease` path, then resume with `--resume
--recover-interrupted --recover-global-lease`. Batch 044 contributes zero
accepted indices; workers `228..233` remain pending until new frozen singleton
children exit successfully.

The first resume safely rejected the still-present block locks before launching
any child. After their attested removal it also safely rejected a redundant
`--recover-global-lease` request: the first attempt had already released the
stale lease. A final frozen resume therefore used `--resume
--recover-interrupted` without that redundant flag. It created
`batch-044.recovery.json`, acquired a fresh lease, and launched batch 045 for
indices `228..233`. Scheduler PID `20176` is the live parent of worker PIDs
`240`, `1484`, `5584`, `10776`, `3516`, and `9844`; scheduler stderr is empty.
