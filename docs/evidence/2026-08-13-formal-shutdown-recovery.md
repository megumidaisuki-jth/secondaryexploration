# Formal bounded-scheduler shutdown recovery, 2026-08-13

## Scope

This is a result-blind operational recovery record. No scientific endpoint,
contrast, interval, direction, gate or claim-level result was read, aggregated
or summarized.

## Interruption diagnosis

The bounded formal scheduler completed batch 030 at 186 canonical artifacts
and then launched batch 031 for singleton indices 186--191. All six children
published their `generate <block-key>` operational message and retained empty
stderr files, but none published an artifact. The create-only final witness
closed the batch with status `batch-failed-stop`; every child has Windows exit
code `1073807364` (`0x40010004`). Windows System event 1074 at
2026-08-11 23:58:24 Asia/Hong_Kong records that
`StartMenuExperienceHost.exe` initiated a user power-off, and event 6006 at
23:58:33 records the Event Log service stopping. The interruption therefore
coincides with an operating-system shutdown rather than a simulation exception
or scheduler memory failure.

The batch witness chain strictly replayed under the frozen scheduler:

- launch raw SHA-256:
  `03ef520d299e2280784608feef50518efd52c0d0e4639845858fb1727f3367b6`;
- started raw SHA-256:
  `87cbef2b7d99accb4629ec36c56e0b89f3a9ee9d0471a79f688e9a076a38c945`;
- final raw SHA-256:
  `d5925338d01cd37cdfc61371a220191f70bdb380fe1884677a1655bc3a4b20ab`;
- launch fingerprint:
  `2318ba1a7768541881a9cebacf8bd799d36747f62deef2491c4c2c6e7ccae644`;
- started fingerprint:
  `d795de5d6e108de7c8f07fc74a4f814bafdde84f6d7f23a8249ab82a85a05669`;
- final fingerprint:
  `bfd12f7d0b93664e69d842090a64a534cdc47719456ea1463db90fdca656aab6`.

Complete operational-history replay returned 186 accepted singleton indices,
32 batches, no unclosed batch and no acceptance of indices 186--191. Thus the
failed batch contributes zero completed indices exactly as registered.

## Stale-lock proof

At recovery inspection there was no formal scheduler, formal singleton child,
confirmation scheduler or progress-checkpoint process; the global scheduler
lease was absent. The block directory contained exactly 186 JSON artifacts,
six locks, zero atomic temporary files and no run summary. None of the six
locked keys had an artifact. Each lock PID exactly matched the corresponding
started witness, and every recorded process identity was absent:

| Worker | Canonical key | PID | Lock SHA-256 |
| ---: | --- | ---: | --- |
| 186 | `n0240-r0002-er_gnm` | 6384 | `835cc29c1b9778b09689bcd488adfc932728892dfbff2fc36801c1d5f47dc4bc` |
| 187 | `n0240-r0002-barabasi_albert` | 18844 | `c334fe4e13c31a6ba28f2627c09d10308cd0819f2b0e3d1eebdcbf48400ce379` |
| 188 | `n0240-r0002-sbm_fixed_count` | 3928 | `bdc68709fa18005abcf3b510d012b5f92c58378abe9a357e23c3265104031141` |
| 189 | `n0240-r0003-er_gnm` | 16532 | `7bcbd1f077009ce37a7384436e0065af515aabebca017b1f19a64192dd2950b2` |
| 190 | `n0240-r0003-barabasi_albert` | 10008 | `a7bea8e80bc88e90613f93b72a96607399e230db3f1cc1dabf11399dad7bff20` |
| 191 | `n0240-r0003-sbm_fixed_count` | 4216 | `d60834fd304379a2a50178df079e448a84cd1d4132729021142b4babb650e9c7` |

These six files are stale process-coordination markers, not scientific
artifacts. Only these exact paths may be removed after independent review.
No JSON artifact, manifest, seed, witness or summary may be changed.

An independent result-blind review reproduced the full batch chain, Windows
shutdown timing, lock contents and hashes, absent process identities, absent
artifacts and quiescent filesystem. It reported that deleting only these six
operational locks and resuming without either recovery flag was consistent
with the frozen contract.

## Resume contract

After independent review, remove only the six attested locks and recheck that
the output has 186 JSON artifacts, zero locks/temporaries, no live cross-phase
runner and no summary. Resume the same session with the frozen CPython,
orchestration revision `02fff817fdde5aea656db881ce4f6dcfca0d37fa`, and
`--resume`. Because batch 031 already has a strict `batch-failed-stop` final
witness, it is closed rather than incomplete; `--recover-interrupted` must not
be supplied. The scheduler must return indices 186--191 to the pending prefix,
and each is accepted only after a new frozen singleton child strictly executes
or replays it and exits successfully.

## Recovery action and witnessed restart

After the independent review, exactly the six attested lock files were removed
with no other filesystem deletion. The post-removal gate observed 186 JSON
artifacts, zero locks, zero temporaries, zero formal processes, no global lease
and no run summary. The same scheduler session was then restarted using only
`--resume`, the frozen CPython executable and orchestration revision
`02fff817fdde5aea656db881ce4f6dcfca0d37fa`.

The scheduler acquired a new global lease and published batch 032 for the
canonical pending prefix 186--191. Its started fingerprint is
`49cb61a35f2e8474918a55e2b424099c194d1b251aa88bcc031765ed5d8e8715`
and its raw SHA-256 is
`59b8817b6ed6ed538b1888b83f27e457fef265b19fb938e8cae1eb6c258b9b24`.
All six recorded children were live with the scheduler as parent, all six
stderr files were empty, all six locks matched the relaunched keys, and the
available-memory gate left approximately 6.50 GiB available immediately after
launch. No interrupted in-memory state or prior failed-batch execution was
accepted.

## Scientific boundary

The 186 existing artifacts retain their original bytes and execution revision
`425710a418b1b28e6c5cd813dff18aeeaa6303c3`. This recovery changes no
scientific design, seed, topology, traffic trace, endpoint, estimand or
inference rule. Formal finalization and inference remain prohibited until the
canonical 240/240 completion witness passes.
