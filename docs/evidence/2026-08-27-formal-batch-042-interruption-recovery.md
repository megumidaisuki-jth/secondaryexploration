# Formal batch 042 interruption recovery

This is a result-blind operational recovery record. No scientific endpoint,
interval, gate, point estimate, or aggregate was read.

## Interrupted state

At `2026-08-27T19:54:29+08:00`, the frozen Formal session
`formal-20260811-memory-v1` had 228 canonical block JSON files. The scheduler
PID `7208`, its parent PID `8072`, and all six batch-042 worker PIDs (`17636`,
`10568`, `6292`, `21852`, `21804`, and `6304`) were absent. The reason for
their termination was not inferred from process absence alone. The global
lease still named scheduler PID `7208`.

Strict result-blind replay accepted exactly the prefix `0..227`, reported 43
batch records, and identified `batch-042.launch.json` as the only incomplete
batch. The canonical registry shape was 228 present of 240 expected, with no
extra, foreign, redirected, or temporary entry. All 258 scheduler stderr
files were empty.

The output contained exactly six stale coordination locks. Their recorded
PIDs were absent, and none of the six locked keys had an artifact JSON:

- `n0240-r0016-barabasi_albert.lock`: `pid=10568`, SHA-256
  `58938500151A9CFD4172063076728EFE201842AB13553AAB35F4E455D51CC79E`;
- `n0240-r0016-er_gnm.lock`: `pid=17636`, SHA-256
  `7DF32C7FC891AF8F680B082097D4EFE69FFE3E6F3244BD24B00735D6D4F08C2B`;
- `n0240-r0016-sbm_fixed_count.lock`: `pid=6292`, SHA-256
  `1335CACF9A775F1D4775D55DA4CC3178E0FC49039AA0EEDA72D15C07B7FEC518`;
- `n0240-r0017-barabasi_albert.lock`: `pid=21804`, SHA-256
  `B4BEBB0B70C5BEAE4563274281DDB45E16FA0D4C30021EFDE8EA31D58141EAAF`;
- `n0240-r0017-er_gnm.lock`: `pid=21852`, SHA-256
  `6C5A04C5B5D505C2EDB60A76B2793329081DD3EFA8715834B4D63F929F598976`;
- `n0240-r0017-sbm_fixed_count.lock`: `pid=6304`, SHA-256
  `42E606F419697D68BC56959247544E1762CB47E97D3FADC656F8BC117C3C5A21`.

## Independent audit and recovery

An independent result-blind read-only audit reproduced the source-snapshot,
session, history, process, lease, registry-shape, lock, temporary-file, and
stderr checks. It approved removal of only the six attested stale locks,
followed by resume with `--recover-interrupted --recover-global-lease`.
Batch 042 contributes zero accepted indices; workers `228..233` remain pending
until strict frozen-child replay exits successfully.

The six whitelisted locks were rehashed immediately before deletion, their
recorded PIDs and corresponding artifact absence were rechecked, and only
those six files were removed. The post-removal state contained 228 block JSON
files, zero locks, and zero temporary files.

The scheduler was restarted with the frozen CPython executable and
orchestration revision `02fff817fdde5aea656db881ce4f6dcfca0d37fa`, using
`--resume --recover-interrupted --recover-global-lease`. It created
`batch-042.recovery.json`, acquired a fresh global lease, and launched batch
043 for indices `228..233`. Scheduler PID `4124` was the live parent of new
worker PIDs `1432`, `12988`, `5920`, `3884`, `21784`, and `8084`. All six
workers were live, six expected locks were present, no scheduler stderr was
nonempty, and approximately 7.12 GiB of physical memory remained available.
