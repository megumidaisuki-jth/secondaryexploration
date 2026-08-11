# Confirmation bounded-memory operational amendment

Status: result-blind design freeze; implementation and independent audit are
required before launch.

Date: 2026-08-11

## Purpose and unchanged scientific contract

The confirmation phase remains the already frozen
`synthetic-confirmation-v1` study. This amendment changes only process
orchestration. It does not change the execution revision, manifest, seed
ledger, parent graphs, traffic traces, topology families, capacity search,
endpoints, estimands, multiplicity procedure, gates, registered scientific
run-summary/phase-evidence/replication-evidence schemas or cross-phase
interpretation rules. The readiness record introduced below is a non-result
operational witness.

Every child must execute exactly one canonical parent-model block by invoking
the frozen runner with logical `--worker-count 240` and one distinct
`--worker-index` in `0..239`. At most six children may be live at once. Worker
count and worker index remain operational selectors and do not enter any
scientific artifact.

## Sequential and result-blind launch gate

Confirmation may start only after all of the following hold:

1. the formal bounded scheduler has a strictly validated 240-block completion
   witness and no formal child, lock or atomic temporary file remains;
2. the formal `synthetic-study-run-summary.v1` has been produced by the audited
   streaming finalizer and strictly replayed against all 240 formal blocks;
3. the formal phase-evidence artifact has been produced by the audited
   streaming analysis revision and strictly replayed against its complete raw
   source chain, after which the analysis tool has atomically published a
   create-only `confirmation-launch-readiness.v1` witness;
4. the frozen confirmation output has no summary, block, lock, temporary,
   symlink or foreign entry;
5. the confirmation manifest, calibration manifest/evidence, precision
   evidence, execution revision and Python environment match their frozen
   fingerprints; and
6. the confirmation scheduler and this amendment are present in one clean,
   committed orchestration revision that is independently audited.

The readiness witness contains only status, formal manifest/summary/evidence
fingerprints, raw file SHA-256 values, execution and analysis revisions, the
240-source registry fingerprint, environment fingerprint, completion time and
result-blind limitations. It contains no interval, bound, gate, estimate,
direction or claim field. The confirmation scheduler validates this witness,
recomputes all referenced raw hashes and source identities, and never loads or
parses the formal phase-evidence JSON. Its control flow is identical for every
possible formal result.

Before launch, the readiness witness itself and its raw SHA-256 must be pinned
in the clean committed confirmation-orchestration authorization revision. The
scheduler verifies the working copy against that Git object before every
batch. A rehashed or replaced readiness file therefore requires a new audited
authorization revision and cannot silently self-authorize confirmation.

Formal phase evidence remains human-embargoed until confirmation is complete.
Once a valid readiness witness exists, confirmation follows the precommitted
automatic path; its launch may not be cancelled, selected or delayed because
of a formal direction or gate. Confirmation cannot rescue, replace or
retroactively alter a failed formal claim.

The following constants are already frozen:

- confirmation manifest fingerprint:
  `dd3caac05a77e89ff69f24dde32930365334b39d4b6cdd5b5d773f5380c3fb5a`;
- execution revision: `425710a418b1b28e6c5cd813dff18aeeaa6303c3`;
- environment fingerprint:
  `0a499b6a1334446fa6bf02a02b25e80934a22689168d6282a2ccb067ac6216c3`;
- precision fingerprint:
  `c2083ff1762ec7407412e702f99bf2c58ef244e4702accc90553112fb876a2d1`;
- base seed: `2026081002`; and
- output root: `outputs/confirmation/synthetic-confirmation-v1`.

The readiness-analysis and orchestration revisions are filled only after their
implementations, tests and independent audits pass.

## Global concurrency and memory gate

The confirmation scheduler must use the same create-only global execution
lease namespace as the formal bounded scheduler. Before confirmation is
authorized, both the formal and confirmation lease acquire/recovery paths must
use one cross-phase runner scanner. In particular, the formal entry point must
refuse stale-lease recovery while a live confirmation child exists, and the
confirmation entry point must symmetrically refuse recovery while a formal
child exists. Holding the lease must
exclude every formal or confirmation runner, including legacy multi-block
commands and singleton commands started outside the active session. Before
each batch, it must:

- prove the lease still belongs to the current scheduler process identity;
- scan for and reject every external formal or confirmation runner;
- prove both phase output roots contain no active lock or atomic temporary;
- read available physical memory; and
- refuse to launch unless at least `4,487,331,840` bytes are available.

The batch size is the lesser of six and the number of pending singleton
indices. A failure, nonempty stderr, source drift, identity mismatch, low-memory
condition, unknown filesystem entry or evidence drift stops all subsequent
launches.

## Immutable provenance

The scheduler creates a new, non-overwritable session directory. Its session
record binds:

- session ID and orchestration revision;
- frozen execution and streaming-analysis revisions;
- absolute Python executable and environment fingerprint;
- exact hashes and semantic fingerprints of every launch-gate source;
- the canonical 240-row index-to-block-key schedule;
- initial confirmation state, which must contain exactly zero blocks; and
- concurrency and memory ceilings.

Every launch-gate source hash, including the readiness witness and every file
it references, is recomputed before each micro-batch and again before
completion. For every micro-batch the scheduler writes create-only launch,
started and final records.
These bind commands, command hashes, worker indices, canonical block keys,
process IDs plus creation identities, UTC timestamps, stdout/stderr paths and
hashes, exit codes, artifact paths and artifact hashes. In a normal batch, a
frozen child contributes only after zero exit, empty stderr and atomic artifact
publication; the frozen child itself performs exact validation before writing.
A failed, partially witnessed or interrupted batch contributes zero indices,
even if one child published an artifact. Each such index becomes accepted only
after a later frozen singleton child strictly replays it and exits successfully.

Completion requires a fresh full-history replay, the exact completed index set
`0..239`, exactly 240 canonical confirmation artifacts, zero lock/temporary or
foreign entries, and current byte hashes matching every accepted batch record.
The completion witness is create-only and count-addressed. The scheduler never
writes the scientific run summary or phase evidence.

## Failure and recovery

Interrupted launch-without-started, partial spawn, nonzero child exit and
scheduler termination are explicit states, not implicit success. Recovery must
first prove that every recorded `(PID, creation identity)` has exited, no
formal or confirmation runner is live, and both output roots are quiescent.
It then writes a create-only recovery record and returns the entire interrupted
batch to pending. Even an atomically published artifact from a failed or
unwitnessed batch is accepted only after a subsequent singleton child strictly
replays that same canonical index and exits successfully.

The scheduler never deletes a lock, temporary file or artifact. Stale-lock
handling requires a separate, explicit recovery witness and independent audit.
An already completed session may return successfully only after complete
revalidation of its completion witness and all 240 current artifacts.

## Required implementation evidence

Before confirmation launch, tests must prove:

- direct equality with the frozen runner's 240 singleton selections, with
  exact, unique and complete block coverage;
- global concurrency never exceeds six, including two-session races and
  external/legacy runner attempts;
- fail-closed handling of low memory, dirty or absent revisions, source or
  environment drift, nonempty stderr, nonzero exit, unknown entries, locks,
  temporaries, symlinks and log collisions;
- launch-without-started, partial-spawn, failed-batch and PID-reuse recovery;
- deletion or rehashed replacement of an early artifact prevents completion;
- existing atomic artifacts retain their exact bytes across resume; resumed and
  uninterrupted fixture paths have identical canonical key coverage,
  `result_fingerprint` values and non-timing scientific witnesses (generation
  and validation timing fields need not be byte-identical); and
- the scheduler never accesses formal interval, gate or point-estimate fields.

Cross-phase lease tests must include a formal-entry attempt to recover a stale
confirmation lease while a confirmation child is live, and the symmetric
confirmation-entry case. Readiness tests must prove that a rehashed, replaced
or missing formal source is rejected before every batch and at completion,
while sentinel result fields that raise on access are never touched.

The implementation must pass the complete project test suite and a separate
read-only audit. Only the resulting committed orchestration revision is
authorized to launch confirmation.
