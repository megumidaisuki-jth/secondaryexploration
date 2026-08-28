# Formal batch 043 interruption recovery

This is a result-blind operational recovery record. No scientific endpoint,
interval, gate, point estimate, or aggregate was read.

## Interrupted state

At `2026-08-28T08:04:34+08:00`, the frozen Formal session
`formal-20260811-memory-v1` still had 228 canonical block JSON files. Scheduler
PID `4124` and batch-043 worker PIDs `1432`, `12988`, `5920`, `3884`, `21784`,
and `8084` were absent. The reason for their termination was not inferred from
process absence alone. The global lease still named scheduler PID `4124`.

Strict result-blind replay validated the frozen sources and session, accepted
exactly indices `0..227`, reported 44 contiguous launches, and identified
`batch-043.launch.json` as the only incomplete batch. The canonical registry
contained exactly the corresponding 228 JSON artifacts, with no extra,
foreign, redirected, or temporary entry. No Formal runner was live. All six
batch-043 stderr files were empty.

Exactly six stale locks remained, and none had a corresponding artifact:

- `n0240-r0016-er_gnm.lock`: `pid=1432`, SHA-256
  `BBFFA550E07A4D04A08179F680ED6F3242C2C6B9545EFB3C89B6C1632EA7B157`;
- `n0240-r0016-barabasi_albert.lock`: `pid=12988`, SHA-256
  `DE725E2B2E26CAA0393385C0C5643E8C3FBF01F14512E34CF86791DFAE497E54`;
- `n0240-r0016-sbm_fixed_count.lock`: `pid=5920`, SHA-256
  `E753FD77109DBB161D9000EE310537B637A78CDD986FA895FD8A22E38604011D`;
- `n0240-r0017-er_gnm.lock`: `pid=3884`, SHA-256
  `BE9DAC6110A6EC8E9EE9C089FA35EE9FF67A1542E645683FA73E1919AACC8CBD`;
- `n0240-r0017-barabasi_albert.lock`: `pid=21784`, SHA-256
  `F6E422DE5DF7C377A130F3A1F0DA9024B70222779D8E6774AE41B041D82B2905`;
- `n0240-r0017-sbm_fixed_count.lock`: `pid=8084`, SHA-256
  `69BE5A64F693734CC5500B8518481312966993F26C011D9E38E434C12C95701D`.

## Independent audit and recovery

An independent result-blind read-only audit reproduced the source, session,
history, process, lease, registry-shape, lock, artifact-absence, temporary-file,
and stderr checks. It approved removing only the six attested stale locks and
resuming with `--recover-interrupted --recover-global-lease`. Batch 043
contributes zero accepted indices; workers `228..233` remain pending until new
frozen singleton children exit successfully.

Immediately before deletion, the exact lock whitelist, hashes, recorded PID
absence, and corresponding artifact absence were rechecked. Only those six
locks were removed. The post-removal state had 228 blocks and zero locks.

The scheduler restarted with the frozen interpreter and orchestration revision
`02fff817fdde5aea656db881ce4f6dcfca0d37fa`, using `--resume
--recover-interrupted --recover-global-lease`. It created
`batch-043.recovery.json`, acquired a fresh lease, and launched batch 044 for
indices `228..233`. Scheduler PID `7380` was the live parent of new worker PIDs
`20288`, `19764`, `19628`, `9880`, `7668`, and `22704`. All six children were
live, the six expected locks were present, and no scheduler stderr was
nonempty.
