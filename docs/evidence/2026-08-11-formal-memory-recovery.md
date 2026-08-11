# Formal execution second recovery and memory correction

## Scope

This is a non-inferential operational record.  No formal endpoint, contrast,
interval, effect direction, or claim-level result was read or summarized.

## Second shutdown and immutable checkpoint

Windows recorded a shutdown at 2026-08-11 00:05 local time and a subsequent
boot at 08:19.  Recovery inspection found 166 complete block JSON files, six
stale per-key locks, no atomic temporary file, no run summary, and no surviving
runner.  None of the six locked keys had a published artifact.  After exact PID,
command, file and temporary-state checks, only those stale operational lock
files were removed.

`tools/formal_progress_checkpoint.py` then strictly replayed all 166 artifacts
under the frozen manifest, ledger, calibration, precision, execution revision,
and CPython 3.12.13 environment.  The create-only checkpoint is
`results/diagnostics/formal-progress-checkpoints/checkpoint-000166.json`, with
fingerprint
`642c31e9fefd36050512783dad46da02baf1d83a8b1f4bb66961a3d275d01d4b`.
An independent audit compared all 166 checkpoint file SHA-256 values with the
current files and found zero mismatch.

Two command-line mistakes occurred while creating the checkpoint.  One shell
timeout orphaned the read-only builder but published no file.  A second attempt
completed validation but supplied a file path where the CLI required an output
directory, so it failed before writing.  The corrected invocation published
the count-addressed checkpoint, and a separate historical replay passed.

## Memory-envelope failure and controlled stop

The six original long-lived shards were restarted only after the frozen
preflight passed.  During resume, each process retained every full artifact it
strictly loaded in its `completed` list.  Once they reached new generation,
their combined working set was about 11.08 GiB, with individual processes at
about 1.709--2.026 GiB.  This was 5.30 times the audited 2.09 GiB six-process
single-block envelope and about 70.2% of the machine's 15.784 GiB physical
memory; available physical memory fell to about 0.459 GiB.

The six processes were therefore stopped by exact PID and command identity
before another artifact was atomically published.  The registry remained 166,
no temporary file existed, and the six resulting stale locks were removed only
after all processes were proved absent.  Available memory returned to about
11.9 GiB.  The cause was cumulative resume retention, not a change in the
single-block simulation algorithm.

Before the operational authorization was fully written, six `worker-count=240`
singleton children were briefly launched as a memory trial.  Independent audit
then correctly required the operational amendment and provenance scheduler to
precede any such launch.  All six trial PIDs were stopped; they published no
artifact, produced empty stderr, left no temporary file, and the registry again
remained exactly 166.  Their stale locks were removed after that verification.
The trial is not counted as formal scheduler execution.

## Corrective boundary

The frozen scientific source under `secondaryexploration/` and execution
revision `425710a418b1b28e6c5cd813dff18aeeaa6303c3` remain unchanged.  Formal
generation may resume only through the independently audited bounded singleton
scheduler described in the 2026-08-11 memory-only operational amendment.  The
old full-memory finalizer and inference path remain disabled until separate
streaming implementations pass byte-equivalence, failure-path, memory, and
independent audits.
