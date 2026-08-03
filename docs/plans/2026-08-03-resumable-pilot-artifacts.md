# Resumable Pilot Artifact Runner

**Date:** 2026-08-03

**Status:** Implemented and independently audited

## Purpose

Tracked pilot blocks can take long enough that an interrupted monolithic run is
unacceptable. The execution layer therefore checkpoints each registered
parent/model block independently, validates it before publication, and rebuilds
one canonical progress summary after every successful checkpoint. Resume is
allowed only for artifacts whose complete study context matches the current
invocation.

## Block artifact contract

Each artifact binds the manifest, semantic seed ledger, parent seed, parent
model, full Git revision, exact Python/platform identity, pipeline version,
wall-clock timings, and final block fingerprint. It also stores the complete
canonical witness used by the block fingerprint. The loader recomputes the
inner result fingerprint and the outer artifact fingerprint independently.

The human- and analysis-facing summary is not trusted as a second source of
truth. Training seeds and demand are regenerated from the ledger and declared
request traces. Parent draw metadata is regenerated from the manifest. Variant
resources, capacity budgets, panels, clique references, held-out identities,
events, accepted counts and values, success rates, state fingerprints, route
arity histograms, and dynamic signaling/coordination costs are re-derived from
the complete witness and checked against every summary field.

## Resume and progress contract

The legal block registry is derived internally as the Cartesian product of
every ledger parent seed and ER, BA, and fixed-count SBM. A caller cannot supply
an expected count or invent a block key. One valid block reports
`in_progress`; only the complete registered set reports `complete`. Records are
canonicalized by block key, duplicates and context mixtures are rejected, and
total generation and exact-validation times are computed from validated block
artifacts.

Existing checkpoints are reusable only under the same manifest, ledger,
parent, model, Git revision, and runtime environment. Formal or confirmation
runs additionally require the CLI revision to equal the revision frozen in the
manifest. Invalid revisions fail before an output directory or expensive block
computation is created.

## Atomic publication

Strict canonical JSON is serialized before touching the destination. Nonfinite
numbers and unsupported values fail closed. A same-directory temporary file is
flushed and file-synchronized, then installed with `os.replace`; failures leave
the prior target unchanged and remove the temporary file. The progress summary
uses the same publication path.

Run the tracked pilot after committing the runner with:

```powershell
python -m secondaryexploration.experiments.runner `
  configs/pilot/synthetic-pipeline-v1.json `
  --workspace-root . `
  --code-revision <full-40-character-commit>
```

## Trust boundary

The two SHA-256 layers detect corruption and mixed execution but are not a
keyed origin signature. An attacker able to coherently replace the entire
witness and both fingerprints is outside this checkpoint threat model. The Git
revision is bound as declared data; a later release wrapper may additionally
compare it with repository HEAD. File data are synchronized before replacement,
but the current Windows-oriented implementation does not claim parent-directory
`fsync` or power-loss durability beyond `os.replace` semantics.
