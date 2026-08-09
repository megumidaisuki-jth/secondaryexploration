# Safe sharding design for formal and confirmation execution

## Problem

The frozen formal runner is deliberately serial.  It writes a progress summary
after each parent-model block, so starting multiple copies against the same
output directory would make workers race to replace `run-summary.json`.  This
is not an acceptable way to reduce wall-clock time.

Each registered parent graph and model is an independent computational unit;
traffic traces are nested within that unit and must not be split across
workers.  The potential execution strategy must therefore partition whole
parent-model blocks, never requests, traces, topology variants, or bootstrap
resamples.

## Accepted interface

The large-size profiling gate has passed, and the frozen runner implements two
mutually exclusive modes:

* `--worker-count N --worker-index K`: preflight all formal identity gates,
  then execute only the canonical block keys whose ordinal has remainder `K`
  modulo `N`.
* `--finalize-only`: preflight the same gates, load every registered artifact
  from disk under exact manifest, ledger, code-revision and environment
  context, require all expected keys, build the canonical complete summary,
  and atomically write `run-summary.json` once.

The serial default remains the single-worker path and retains its existing
resumable progress summary behavior.  Shard workers never write the shared
run summary.

## Required invariants

1. Canonical ordering is the existing ledger order followed by the registered
   model order.  For any fixed `N`, shards form an exhaustive, disjoint
   partition of that exact ordered key tuple.
2. Each worker runs the same frozen-manifest, precision, calibration and
   execution-source verification before reading or writing a block.
3. Each worker generates, fully exact-replays, and atomically writes only its
   own unique `blocks/<key>.json` artifacts.  A per-key exclusive creation lock
   prevents accidental duplicate workers from concurrently generating the same
   key; an existing validated artifact follows the normal resume path.
4. Artifact validation during both resume and finalization binds the complete
   scientific witness to the expected manifest, seed ledger, parent seed,
   model, code revision and environment.  Finalization has no path that
   accepts an incomplete set as a complete study.
5. A failed worker leaves either no artifact or a complete atomically written
   artifact.  It cannot publish a malformed summary.  Only a successful
   finalizer may create the complete summary.
6. No worker shares a parent graph across a boundary.  The effective
   statistical sample remains the registered parent graph within its model
   stratum, exactly as in the frozen inference plan.

## Verification contract

* Unit-test the partition for every worker count from 1 through a bound larger
  than the 240 formal keys: no duplicate keys, exact coverage, deterministic
  ordering and rejection of invalid worker arguments.
* Integration-test two small workers writing a common temporary output root;
  assert that no summary appears until finalization, every resulting artifact
  validates in its expected context, and finalization yields byte-identical
  canonical summary content regardless of worker completion order.
* Test interruption, malformed artifact, missing key and duplicate-worker
  lock paths; all must fail closed without replacing a valid complete summary.
* Compare a representative frozen block's result fingerprint and artifact
  witness between serial and shard execution.  Only orchestration timing may
  differ.
* Because this changes `secondaryexploration/experiments/runner.py`, rerun the
  full test suite, obtain an independent audit, and regenerate both manifests
  with a new clean code revision before launching either formal phase.

## Non-inferential progress checkpoints

Shard workers deliberately do not publish a partial scientific summary.
Operational progress is instead frozen with
`tools/formal_progress_checkpoint.py`.  The checkpoint strictly loads every
completed artifact under the manifest, seed ledger, calibration, precision,
execution revision and runtime environment, then records only canonical block
keys, file SHA-256 values, artifact/result fingerprints and completion counts.
It neither copies endpoint values nor computes contrasts, so it cannot be used
for optional stopping or early claim selection.

A historical checkpoint must remain replayable after later blocks finish.
The loader therefore requires every checkpointed block to retain exactly the
same bytes and scientific fingerprints while allowing the current canonical
block registry to be a strict superset.  Unknown block entries, a missing or
changed checkpointed artifact, source-identity drift, count drift, key
reordering and fingerprint tampering all fail closed.  Such a checkpoint is a
progress and integrity witness only; it never replaces the complete 240-block
finalizer or the frozen inference gates.
