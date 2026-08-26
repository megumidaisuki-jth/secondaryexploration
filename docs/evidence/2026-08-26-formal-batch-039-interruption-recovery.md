# Formal batch 039 interruption recovery

This is a result-blind operational recovery record. No scientific endpoint,
interval, gate, point estimate, or aggregate was read.

## Interrupted state

At `2026-08-26T14:12:04+08:00`, the frozen Formal session
`formal-20260811-memory-v1` had 220 canonical block JSON files. Strict replay
of the scheduler history passed with an accepted prefix of indices `0..215`,
40 batch records, and `batch-039.launch.json` as the only incomplete batch.
All source snapshots were verified against orchestration revision
`02fff817fdde5aea656db881ce4f6dcfca0d37fa`.

The batch-039 started witness records scheduler PID `4436` and worker PIDs
`3744`, `25656`, `22632`, `10836`, `25604`, and `25424`. All seven recorded
process identities were absent. No Formal runner was live. The global lease
still named scheduler PID `4436`; its SHA-256 was
`1CE5D9CCA3BF9280567858324A2241A94597AB3C993218C383DEA243356E24F7`.

The output was quiescent apart from exactly two stale coordination locks:

- `n0240-r0012-barabasi_albert.lock`: `pid=25656`, SHA-256
  `08461A24B707A372002543B9CC61691D2F7833BAC8BABC3ABEA17819A856BB24`;
- `n0240-r0013-barabasi_albert.lock`: `pid=25604`, SHA-256
  `2C8B73F55C773F5B6165F5F353C60A8644E3BB05E509299BE1E00CF11F402EBF`.

There were zero atomic temporary files and zero nonempty scheduler stderr
files. Neither locked key had an artifact JSON.

## Independent audit and recovery contract

An independent result-blind read-only audit reproduced the process, lease,
lock, artifact-count, temporary-file, stderr, source-snapshot, session-record,
and batch-history checks. It approved deletion of only the two attested stale
lock files above, followed by resume with `--recover-interrupted` and
`--recover-global-lease`.

The interrupted batch contributes zero accepted indices. Recovery must close
batch 039 with a create-only recovery witness and return all six indices
`216..221` to pending. Each index is accepted only after a new frozen singleton
child strictly executes or replays it and exits successfully. Existing atomic
artifacts are retained byte-for-byte; no artifact, manifest, seed, summary, or
scientific evidence may be deleted or edited.

## Recovery action and witnessed restart

After the independent audit, exactly the two attested lock files were removed.
The immediate post-removal gate observed 220 block JSON files, zero locks, and
zero temporary files. No other path was removed.

The frozen scheduler was restarted with the same CPython executable and
orchestration revision using `--resume --recover-interrupted
--recover-global-lease`. It published the create-only
`batch-039.recovery.json` witness, acquired a fresh global lease, and launched
batch 040 for indices `216..221`. Scheduler PID `7208` was the parent of all
six new singleton children. Their PIDs were `8788`, `8832`, `14464`, `9212`,
`3056`, and `16416`, respectively. All six were live, the two expected BA
locks named the new PIDs, all scheduler stderr files were empty, no temporary
file existed, the block count remained 220, and approximately 6.05 GiB of
physical memory remained available. The six child processes were assigned
High priority with priority boost enabled.
