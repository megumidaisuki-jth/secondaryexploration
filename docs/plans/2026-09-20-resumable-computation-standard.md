# Resumable computation standard

All new long-running computations in this project must be designed as resumable jobs rather than opaque single-process runs.

## Required execution properties

1. Partition work into deterministic, independently verifiable units.
2. Write each completed unit atomically to a checkpoint bound to input hashes, code revision, and runtime contract.
3. Maintain an endpoint-free `progress.json` with completed-unit count, total-unit count, current status, and update time.
4. On restart, validate the checkpoint context and reuse only intact matching checkpoints; malformed, partial, or drifted checkpoints must be recomputed.
5. Keep raw inputs immutable. A checkpoint or final artifact must never overwrite a non-identical prior artifact.
6. Use bounded local parallelism chosen from measured memory headroom, not unrestricted worker counts.
7. Write explicit execution receipts with command, timestamps, exit status, output hash, and input-context hash.
8. After successful completion, archive final artifacts, checkpoints, receipts, and diagnostics to the project Git remote using an allowlisted set of paths.

## Interpretation boundary

Checkpointing, parallelism, and execution receipts establish operational recoverability. They do not substitute for the independent scientific replay audit required before results are interpreted, plotted, or reported.
