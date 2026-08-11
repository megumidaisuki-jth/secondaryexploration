# Formal execution memory-only operational amendment

## Timing and evidentiary boundary

This amendment was made on 2026-08-11 after 166 of 240 formal parent-model
blocks had completed and before any formal endpoint, contrast, interval, or
claim-level result was read.  The immutable checkpoint is
`checkpoint-000166.json`, fingerprint
`642c31e9fefd36050512783dad46da02baf1d83a8b1f4bb66961a3d275d01d4b`.

The amendment changes only process orchestration and later memory management.
It does not change the manifest, parent graphs, seeds, models, traffic traces,
topology constructors, capacity matching, estimands, endpoint horizon,
hierarchies, bootstrap streams, multiplicity correction, confirmation gate,
artifact schema, or execution revision
`425710a418b1b28e6c5cd813dff18aeeaa6303c3`.

## Trigger

The original six whole-block shards were safe as a partition but unsafe as a
long-lived process layout.  Each resumed process retained every previously
loaded full artifact in its `completed` list.  At 166 completed blocks the six
processes held about 11.08 GiB, 5.30 times the audited six-single-block runtime
envelope, leaving about 0.459 GiB available physical memory.  They were
therefore stopped before another artifact was published.  The registry stayed
at 166, and the abandoned pre-amendment singleton trial likewise published no
artifact.

## Authorized execution layout

The phrase “six resumable whole-block shards” in the earlier sharding plan is
superseded operationally as follows:

1. There are exactly 240 logical shards, indices 0 through 239.  Under the
   frozen runner each contains exactly one canonical parent-model block.
2. At most six singleton child processes may be live concurrently.  A child
   runs the unchanged frozen runner with `--worker-count 240` and its unique
   `--worker-index`, performs the same strict preflight and full replay, and
   exits immediately after its single block.
   A fixed global create-only lease permits only one bounded scheduler session
   at a time, and every micro-batch also rejects any externally launched formal
   runner, including the superseded six-shard command.  A stale lease may be
   removed only through explicit recovery after its exact PID/creation identity
   and all formal runner processes are proved absent.
3. Before each micro-batch, available physical memory must be at least twice
   the audited six-single-block envelope: 4,487,331,840 bytes.  A lower value
   stops new launches.
4. Existing blocks are also assigned to singleton children once per scheduler
   session so their strict replay and zero exit are witnessed; the scheduler
   never treats mere file existence as validation.
5. Any nonzero exit, nonempty stderr, missing artifact, active lock, atomic
   temporary entry, foreign block, source drift, interpreter drift, log
   collision, or existing run summary stops further launches.  The scheduler
   never removes or steals a lock.
6. Every session and micro-batch uses create-only plan, started, and final
   witnesses binding the
   orchestration revision, interpreter, frozen sources, checkpoint-166,
   canonical index/key assignment, commands, exact PID/parent/creation
   identities, times, exit codes, log
   hashes, artifact byte hashes, and observed concurrency.
7. After a machine interruption, recovery is explicit: all matching singleton
   runner processes must be absent and an operator must first resolve and
   document stale locks.  A create-only recovery witness records whether each
   interrupted key has an atomic file or no file, but does not accept that file
   as scientifically valid.  Every interrupted index remains pending and must
   pass the unchanged child's strict replay before it can be finalized.
   If interruption occurs before a complete started/PID witness is published,
   recovery records that limitation explicitly and relies on the global formal
   runner scan plus the quiescent lock/temporary-file gate; the entire planned
   batch still remains pending.  PID reuse is distinguished by process creation
   identity, not PID number alone.
   Likewise, if any child exits nonzero or writes stderr, the failed batch is a
   closed provenance record but accepts zero completed indices: every index in
   that batch, including one that atomically published a file, must be replayed
   successfully by a later frozen child.
8. A completion witness is published only after replaying the entire operational
   hash chain again and proving that the current block directory contains
   exactly the 240 expected canonical keys with the same bytes recorded by
   their successful singleton batches.

The scheduler is an analysis/operations tool outside `secondaryexploration/`.
It has its own committed orchestration revision.  This does not re-freeze or
invalidate the scientific execution revision or any of the 166 artifacts.

## Downstream memory gate

The old `runner --finalize-only` and the current non-streaming formal inference
path must not be used for a 240-block phase.  Before finalization, a separately
revision-bound streaming implementation must strictly load one artifact at a
time, retain only the light summary/analysis projection, reproduce the exact
v1 summary and evidence bytes on fixtures, pass failure-path and memory tests,
and receive independent audit.  This is an implementation gate only; the
registered statistical contract remains unchanged.
