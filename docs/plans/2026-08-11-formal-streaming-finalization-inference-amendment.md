# Formal streaming finalization and inference amendment

## Timing and scope

This implementation-only amendment was written on 2026-08-11 after 166 of
240 formal parent-model blocks had completed, while formal execution remained
result-blind. No formal endpoint, contrast, interval, hierarchy decision, or
claim-level result was read to design this change. The pre-change registry is
bound by `checkpoint-000166.json`, fingerprint
`642c31e9fefd36050512783dad46da02baf1d83a8b1f4bb66961a3d275d01d4b`.

The scientific execution revision remains
`425710a418b1b28e6c5cd813dff18aeeaa6303c3`. Existing and future block
artifacts therefore retain one execution contract. The streaming tool has a
separate, committed `analysis_revision`; changing analysis memory management
does not re-freeze the execution revision or invalidate any completed block.

## Trigger and prohibited paths

The frozen runner's legacy `--finalize-only` path retains every full block
artifact. The former formal-inference loader did the same and cross-phase
replication could retain both raw phase chains. At the projected 240-block
size, Python object expansion on this 16 GiB host has no credible safe
envelope. Those legacy whole-phase paths are prohibited for formal and
confirmation output.

## Authorized streaming contract

1. Finalization enumerates the exact canonical block registry, requires an
   empty lock directory and no foreign, temporary, redirected, missing, or
   extra block entry, and strictly loads one complete artifact at a time.
2. After strict validation it retains only the v1 summary fields and the raw
   file SHA-256, releases the full artifact, and proceeds to the next block.
   A second raw-file hash pass detects mutation during the streaming scan.
3. The resulting `run-summary.json` uses the existing
   `synthetic-study-run-summary.v1` schema, canonical order, totals, source bindings, and
   fingerprint calculation. It must be semantically and byte-canonically
   identical to the legacy builder for the same immutable artifacts.
4. Phase inference repeats the same one-artifact strict replay against the
   complete summary. For each artifact it retains only the registered 70
   trace-level contrast rows, the demand-aware activity flag, the artifact
   fingerprint, and the light summary record, then releases the artifact.
5. All registered estimands, the 4:3 held-out aggregation, parent as the
   independent unit, three-model equal weighting, 20,000 shared bootstrap
   resamples, tail probability 1/1600, eight five-contrast hierarchies,
   secondary gates, censored-event coverage rule, evidence schemas, phase
   separation, and confirmation state machine remain unchanged.
6. Cross-phase replication strictly replays and validates the formal phase,
   reduces it to the 40 registered intervals plus source provenance, releases
   its raw rows and bootstrap arrays, and only then performs the corresponding
   confirmation replay. It never pools phases and requires disjoint phase
   source registries.
7. Finalization publishes a create-or-identical witness binding the analysis
   revision, execution revision, manifest and summary fingerprints, and all
   240 raw block hashes. Scientific endpoints and contrasts are absent from
   this finalization witness.
8. A complete summary, phase evidence, or replication evidence is published
   only after full strict replay. Existing non-identical outputs are never
   overwritten.

## Verification gate

Before first formal use, the committed streaming implementation must pass:

- exact legacy-versus-stream summary and phase-evidence equivalence tests on
  non-formal fixtures;
- an object-lifetime test proving that no more than one full block artifact is
  retained by finalization;
- strict missing, foreign, redirected, source-tamper, and concurrent-mutation
  rejection tests;
- sequential cross-phase projection tests proving that raw trace rows and
  bootstrap arrays are released before the next phase;
- the full repository test suite and an independent read-only audit.

Only the committed and audited analysis revision may be supplied to the
streaming CLI. This gate changes memory behavior only; it authorizes no change
to the frozen statistical or scientific contract.
