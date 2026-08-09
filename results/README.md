# Results and evidence artifacts

This directory contains compact, reviewable evidence derived from strict source
chains. Bulk execution artifacts remain under `outputs/` and are excluded from
ordinary Git commits because formal blocks are multi-megabyte replay witnesses.
A final data manifest and archival deposit will be prepared before submission.

Tracked result classes include:

- `gate-v1-prior-paper/`: prior-paper semantic reproduction evidence;
- `pilot/`: completed pilot and calibration summaries/evidence;
- `planning/`: the audited formal precision freeze;
- `diagnostics/formal-runtime-profile-batch-v1/`: the immutable raw six-worker
  runtime batch and its launch/finalization witnesses;
- `diagnostics/formal-runtime-profile-evidence-v1.json`: the strict runtime
  launch-gate evidence; and
- `diagnostics/formal-progress-checkpoints/`: create-only, count-addressed
  progress and integrity witnesses.

Formal progress checkpoints contain only canonical block keys, source
fingerprints, file hashes, artifact/result fingerprints and completion counts.
They do not contain endpoint values, effect estimates, intervals or hierarchy
decisions and cannot be used for optional stopping. A historical checkpoint
must replay after the local output becomes a valid strict superset.

No incomplete formal or confirmation phase is a scientific analysis input.
Inferential evidence is written only below `results/inference/` after a complete
240-block summary has been rebuilt and strictly replayed.
