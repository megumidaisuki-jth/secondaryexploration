# Formal progress checkpoint at 174 blocks

## Scope

This is a non-inferential operational record. No formal endpoint, contrast,
interval, effect direction, gate state or claim-level result was read,
aggregated or summarized.

## Snapshot and publication

The bounded formal scheduler had atomically published 174 of the 240 canonical
parent-model blocks while six singleton children for worker indices 174--179
were active. A progress-checkpoint builder captured the 174-file historical
registry and strictly replayed it under the frozen formal manifest, seed
ledger, calibration evidence, precision evidence, execution revision
`425710a418b1b28e6c5cd813dff18aeeaa6303c3`, environment fingerprint and
CPython 3.12 runtime. Concurrent formal execution was permitted to become a
strict superset; it was not paused and its active locks were neither removed
nor modified.

The create-only artifact is
`results/diagnostics/formal-progress-checkpoints/checkpoint-000174.json`. It
records 174 blocks and has checkpoint fingerprint
`db4039d4f754245261f60d0fef21607c681790c3d5f961a439072e2da64a2624`.
The successful builder emitted an empty stderr stream and no temporary or
replacement output was retained.

## Operator error and corrective hardening

The first builder command incorrectly supplied the intended count-addressed
file as `--output`; the CLI contract required the frozen output directory.
After confirming the exact auxiliary PID and command identity, that read-only
process was stopped before publication. It had created no checkpoint and did
not modify any formal artifact, lock or scheduler record. The correctly
parameterized builder was then launched once with the frozen directory.

Commit `c91e989` moved output-directory validation ahead of the expensive
strict replay, so the same file-shaped argument now fails before the builder is
called. Commit `7631b08` additionally requires lexical canonical paths and
rejects symlink or Windows reparse components before both generation and
historical replay. The focused checkpoint suite passed 11 tests, and the full
repository suite passed 435 tests with one Windows privilege-dependent symlink
test skipped.

## Independent verification

Structural validation of the published checkpoint passed. A separate
streaming SHA-256 pass compared every recorded file digest with the current
historical file and found 174 matches and zero mismatches. The checkpoint raw
file SHA-256 is
`26fc0b25d902382176e248417614bcfa57fecb95a87ca527913a0a9fd19cec8a`.

An independent official historical replay initially used the machine's
default Miniconda interpreter; the frozen environment gate rejected it before
artifact replay. The audit was restarted once with the formal session-bound
CPython executable and completed in 1,389.8 seconds. It invoked the strict
artifact loader 174 times and confirmed all of the following:

- schema, outer fingerprint and complete source identity chain;
- `completed_block_count = 174` and exactly 174 unique registry rows;
- the canonical first-174 block order;
- 174/174 raw file SHA-256, artifact fingerprint and result fingerprint
  matches; and
- exact equality between the official replayed object and the published
  checkpoint.

At replay completion the live canonical registry was still exactly 174, with
six active locks. The locks did not prevent historical replay. The separately
tested official loader also accepts a valid current strict superset, but this
specific live audit did not observe a strict superset and makes no such claim.
The independent audit reported zero Blocker, P1 or P2 findings.

## Scientific boundary

This checkpoint is operational provenance only. It does not replace the
complete 240-block run summary, formal phase evidence, confirmation phase,
cross-phase replication evidence or registered result-reporting gates.
