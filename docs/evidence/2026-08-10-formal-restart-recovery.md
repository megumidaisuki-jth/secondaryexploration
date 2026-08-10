# Formal execution restart recovery, 2026-08-10

This note records an operational recovery only. It contains no scientific
endpoint, contrast, effect estimate or inferential readout.

## Interruption diagnosis

The first six-shard run stopped during the size-60 layer. Windows System log
events record a system-initiated shutdown transition at 2026-08-09 23:57:46
Asia/Hong_Kong and a subsequent boot at 2026-08-10 08:37:33.5. The six worker
stdout files stopped between 23:47 and 23:55; all six stderr files remained
empty.

Before recovery, the canonical block directory contained 78 JSON artifacts
and the lock directory contained these six entries:

- `n0060-r0006-er_gnm.lock` (`pid=18880`)
- `n0060-r0006-barabasi_albert.lock` (`pid=23532`)
- `n0060-r0006-sbm_fixed_count.lock` (`pid=24144`)
- `n0060-r0007-er_gnm.lock` (`pid=24312`)
- `n0060-r0007-barabasi_albert.lock` (`pid=20452`)
- `n0060-r0007-sbm_fixed_count.lock` (`pid=22476`)

No corresponding block artifact or atomic temporary file existed for any of
the six keys. Five recorded PIDs were absent. PID 20452 had been reused after
the reboot by an unrelated `ChatGPT.exe` storage-service process; its process
identity and creation time did not match the pre-reboot Python worker. No
formal Python worker remained live.

The historical 60-block checkpoint was replayed in the interrupted state and
passed with fingerprint
`6baea492d11f114ea0414a2445a8b7daa2ab55bfc9938627974e27caeb464f8a`.
This proves that every checkpointed artifact retained its exact bytes and
registered identity; it does not inspect or summarize scientific endpoints.

## Recovery action

Only the six verified stale lock files above were removed. They were
unrecoverable process-coordination markers, not study artifacts; no completed
block, summary, manifest, seed, result witness or scientific record was
deleted or changed.

The frozen preflight was then rerun with CPython 3.12.13 and passed with:

- execution revision
  `425710a418b1b28e6c5cd813dff18aeeaa6303c3`;
- environment fingerprint
  `0a499b6a1334446fa6bf02a02b25e80934a22689168d6282a2ccb067ac6216c3`;
- formal manifest fingerprint
  `ac7152fc11b79c61b1ec14dc24b26d0ee60d159b00ddaa396e166651212191a6`;
- precision fingerprint
  `c2083ff1762ec7407412e702f99bf2c58ef244e4702accc90553112fb876a2d1`;
- exact 240-block registry and 40 blocks assigned to each of six workers.

At 2026-08-10 09:21:09 Asia/Hong_Kong, the same six canonical shards were
relaunched in resume mode. New process IDs were 21860, 22252, 21840, 18660,
8336 and 11408 for worker indices 0 through 5, respectively. Logs are retained
under
`outputs/formal/synthetic-formal-v1/shards/formal-six-worker-resume-2026-08-10-v1/`.
All six processes were observed live and each reacquired exactly one canonical
block lock after strictly replaying its already completed artifacts.

## Validity boundary

Resume mode does not substitute, impute or continue an interrupted in-memory
block. Each unpublished interrupted key is regenerated deterministically and
must pass the same exact result validation before one atomic artifact appears.
Existing artifacts are strictly replayed before being accepted. The canonical
240-block finalizer, formal inference gate and independent confirmation phase
remain unchanged.
