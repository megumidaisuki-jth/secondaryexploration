---
experiment_id: confirmation-20260831-memory-v1
study_id: synthetic-confirmation-v1
phase: confirmation
status: structurally_complete_pending_independent_audit
paper_ready: false
completed_utc: 2026-09-13T14:35:32Z
raw_block_count: 240
raw_data_bytes: 4024126383
raw_data_storage: git_lfs
configuration_sha256: 95555bd62fc7f8490596c2dad389799d73fa59dcb71cee57247da0a403b9a7fb
completion_witness_sha256: b4e511c5274b33d08a02aa8b4ede578cb47bb57f3c992bf860d804d10f16adfb
latest_batch_final_sha256: 037bd9c98982ce0a615242286b878efa9a0a7eb9e17327021b5626aeed44da17
execution_revision: 425710a418b1b28e6c5cd813dff18aeeaa6303c3
orchestration_revision: f0b2f246dccec7bd20b9215870e8971687f9496d
analysis_revision: 9ecaadec84f8bebe799fb507969de8e0a0947b66
runtime: Python 3.12.13
environment_fingerprint: 0a499b6a1334446fa6bf02a02b25e80934a22689168d6282a2ccb067ac6216c3
archive_commit: b5c0d9043f704570230de9072c2b165b41cdc8e5
---

# Confirmation experiment archive

Subsequent checkpoint (2026-09-17): the Confirmation summary and finalization
witness have now been generated and their byte bindings verified. The tables
below retain the original raw-archive-time state. See
`docs/evidence/2026-09-17-post-confirmation-analysis.md` for the ongoing analysis
pipeline and remaining independent replay/reporting gates.

## Purpose and boundary

This is the archived raw-data record for the pre-registered Confirmation phase
of `synthetic-confirmation-v1`. It records execution and integrity facts only.
It deliberately contains no estimated effects, interval bounds, directions,
contrasts, gate decisions, or manuscript claims. Those are produced only after
the independent result-blind audit and the frozen finalization procedure.

## Frozen design

- Manifest: `configs/confirmation/synthetic-confirmation-v1.json`
  (`SHA-256 95555bd62fc7f8490596c2dad389799d73fa59dcb71cee57247da0a403b9a7fb`).
- Base seed: `2026081002`; demand-aware seed family: `fhs5`.
- Size cells: 30, 60, 120, and 240 nodes; each uses 20 parent replicates.
- Parent-network generators recorded in the raw block names: `barabasi_albert`,
  `er_gnm`, and `sbm_fixed_count`. Thus the archived registry contains
  `4 × 20 × 3 = 240` singleton raw blocks.
- Routing/topology families: `demand-aware`, `fhs3`, `fhs5`, and `nch`, with
  maximum hyperedge arities 3 and 5.
- Each configuration uses 12 requests per node, per-node capital 120, three
  amount weights `(1,6)`, `(3,3)`, `(6,1)`, and the manifest's frozen training
  and shifted test regimes. Consult the manifest—not this log—for the complete
  machine-readable parameter set.

## Environment and code identity

The execution package revision was
`425710a418b1b28e6c5cd813dff18aeeaa6303c3`; scheduler/readiness orchestration
was `f0b2f246dccec7bd20b9215870e8971687f9496d`; and final analysis tooling is
frozen to `9ecaadec84f8bebe799fb507969de8e0a0947b66`.

The frozen runtime was Python 3.12.13. Its canonical environment fingerprint,
including implementation and platform fields, was
`0a499b6a1334446fa6bf02a02b25e80934a22689168d6282a2ccb067ac6216c3`.
The scheduler was not allowed to resume under the later Python 3.12.14 runtime;
the fixed 3.12.13 environment was restored and fingerprint-checked before the
final resumed batch.

## Raw-data archive

| Item | Repository path | Preservation method |
| --- | --- | --- |
| 240 raw blocks (4,024,126,383 bytes) | `outputs/confirmation/synthetic-confirmation-v1/blocks/` | Git LFS pointers and LFS objects |
| Scheduler session and 41 finalized batch witnesses | `results/diagnostics/confirmation-bounded-scheduler/confirmation-20260831-memory-v1/` | ordinary Git |
| Final batch witness | `results/diagnostics/confirmation-bounded-scheduler/confirmation-20260831-memory-v1/batch-044.final.json` | ordinary Git; SHA-256 in frontmatter |
| Completion witness | `results/diagnostics/confirmation-bounded-scheduler/confirmation-20260831-memory-v1/completion.json` | ordinary Git; SHA-256 in frontmatter |

Every Git LFS pointer records the SHA-256 object identity and exact byte size of
its raw block. The completion witness records the canonical whole-registry
fingerprint. These two layers must be retained together and must not be edited.
At archive time there were 696 scheduler-diagnostic files, 41 finalized batch
witnesses numbered through `batch-044`, zero live scheduler processes, zero
block locks, and zero temporary entries. Batch numbers 027, 032, 033 and 041 do
not have a final witness because those launches were interrupted/recovered;
their launch, worker and recovery traces remain archived. They are not missing
raw blocks: the terminal registry contains all 240 canonical block names.

## Execution and recovery history

The run used bounded batches of at most six singleton blocks to respect the
frozen memory envelope. Intermediate resumes were performed only after
result-blind checks of process ownership, global lease state, block count,
lock count, temporary entries, and the newest batch-final JSON. The archived
diagnostic directory retains each batch's launch, start, worker stdout/stderr,
and final witnesses, plus the boundary pause/recovery records.

The terminal batch (`batch-044`) completed the registry at 240/240. The
completion witness and its batch final were parsed as strict JSON after the
scheduler exited; no locks or temporary files remained. The scheduled recovery
task was then disabled to protect the finished raw data from accidental reruns.

## Recovery and verification procedure

1. Clone the repository and fetch the exact archive commit (or a descendant).
2. Run `git lfs pull` before accessing the raw blocks. A normal clone alone
   contains only LFS pointers.
3. Verify the manifest and the frontmatter SHA-256 values with `Get-FileHash`
   (PowerShell) or `sha256sum` (Unix).
4. Verify that `blocks/` contains exactly 240 JSON files and that `.locks/`
   and `temp/` are absent or empty. Treat the `completion.json` byte registry
   as the integrity authority.
5. Use only the frozen Python 3.12.13 environment and the recorded execution
   revision for any structural replay. Do not invoke the scheduler to create a
   second Confirmation run over this completed archive.
6. Before inspecting or reporting scientific endpoints, run the independent
   result-blind audit, then the frozen streaming finalization and phase-evidence
   commands. Keep Formal and Confirmation evidence streams separate.

## Paper-writing handoff

The archived blocks, manifest, scheduler witnesses, code revisions, runtime
fingerprint, and LFS provenance are sufficient to reproduce the computation
without rerunning it. They are not yet a paper-ready result package. The
following fixed outputs are still intentionally absent at raw-data archive
time and must be generated from the saved blocks:

| Required paper asset | Fixed path or scope | Archive-time state |
| --- | --- | --- |
| Confirmation run summary | `outputs/confirmation/synthetic-confirmation-v1/run-summary.json` | not generated |
| Confirmation finalization witness | `results/diagnostics/formal-streaming-finalization/confirmation-finalization-witness.json` | not generated |
| Confirmation phase evidence | `results/inference/confirmation-phase-evidence.json` | not generated |
| Formal descriptive projection | `results/inference/formal-descriptive-mechanism-v1.json` | not generated |
| Confirmation descriptive projection | `results/inference/confirmation-descriptive-mechanism-v1.json` | not generated |
| Forty-record cross-phase replication evidence | `results/inference/formal-confirmation-replication-evidence.json` | not generated |
| Canonical machine-readable source-data export | all registered contrasts, parent strata, coverage, activity, 13 descriptors, runtime and fingerprints | not generated |
| Paper figures and tables | Figures 1–3, Table 1 and supplementary/source-data tables | not generated |

The eventual source-data export must retain all 40 registered contrasts in
each phase, all 40 cross-phase records, all parent-model values, all `q=0.10`
coverage cells, every demand-aware changed/unchanged activity cell, all 13
descriptive metrics across four source families, four sizes, three parent-model
strata and both phases, plus runtime and source fingerprints. No row may be
discarded based on direction, interval, gate state or replication state.

Accordingly, no simulation rerun is needed. The remaining work is analytical:
independent result-blind audit, frozen streaming finalization, phase evidence,
both descriptive projections, cross-phase evidence, canonical source-data
export, and manuscript tables/figures. Any statement in the manuscript must
cite those post-audit derived artifacts rather than raw block contents alone.
