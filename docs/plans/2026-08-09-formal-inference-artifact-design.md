# Formal and confirmation inference artifact contract

## Amendment status and launch boundary

This contract defines the only route from the completed synthetic formal and
independent-confirmation phases to confirmatory claims.  It is a
post-launch, pre-inferential-analysis amendment dated 2026-08-09.  Fifteen of
240 formal blocks had completed when the formal workers were paused.  One
held-out record was viewed only to identify the artifact field layout; no
interim effect aggregation, confidence interval, hierarchy decision, or
formal-versus-confirmation comparison was computed.

The analysis schema, algorithms, state machine and strict replay tests are
implemented before the formal workers resume.  They live outside the
execution package so the simulation snapshot remains exactly revision
`425710a418b1b28e6c5cd813dff18aeeaa6303c3`.  This timing and the amendment's
scope must be disclosed with the preregistration record; it must not be
described as part of the earlier precision freeze.

No partial run summary, loose block JSON, or manually assembled table is an
analysis input.  A phase can be analysed only after the runner has rebuilt a
`status=complete` summary from all 240 registered block artifacts.

## Strict inputs

For each phase, the evidence generator uses this fixed trust-chain order:

1. strict-load the phase manifest and rebuild its exact seed ledger;
2. strict-load the audited calibration evidence and then replay the
   recommended-A precision artifact from that basis;
3. derive the canonical 240-block registry from the manifest and ledger;
4. strict-load a `status=complete` summary and require its block registry to
   equal the derived registry exactly;
5. resolve blocks only from the summary's canonical registered relative paths;
6. load each block through the hash-attested artifact loader under its exact
   parent seed, model, summary revision and environment;
7. rebuild the complete summary from those blocks and require exact equality;
8. build the phase evidence, replay it from the same sources, and only then
   atomically write it.

Formal and confirmation evidence remain separate.  The sets of their manifest,
ledger, summary, block-artifact, paired-manifest and evidence SHA-256
fingerprints must have empty intersection; any repeated digest fails closed.

## Trace-level primary contrasts

For each held-out trace and each source family (`demand-aware`, `fhs3`,
`fhs5`, `nch`), the reference arm is the exact equal mean of only the binary
variant IDs registered for that source by the block's `resource_panels` entry.
Binary arms registered to other source families are excluded.  Binary variants
are never promoted to independent observations.

For horizon `H`, source value `S`, and binary-arm values `B_j`, the two primary
source-minus-reference contrasts are:

- normalized restricted no-path time:
  `S.tau_nopath.request_index / H -
  mean_j(B_j.tau_nopath.request_index / H)`;
- fixed-horizon failure risk:
  `I(S.tau_nopath observed) - mean_j I(B_j.tau_nopath observed)`.

The global trace contrast is the equal mean of the four already panel-matched
source-family trace contrasts.  It has no separate binary bracket of its own.
Thus the global endpoint is not weighted by the number of source or binary
variants.

The artifact schema requires `tau_nopath.request_index=H` whenever an event is
administratively censored.  A different censored request index is invalid.

Each trace observation retains the paired-manifest fingerprint already stored
in the block artifact.  It is invalid to fabricate a study-level digest in
place of this trace-level provenance witness.

## Nested traces and independent parents

Within each exact `(phase, size, parent model, parent replicate)` block:

1. compute the four same-distribution trace contrasts and average them
   equally;
2. compute the three distribution-shift trace contrasts and average them
   equally;
3. combine the two scope means with the frozen `4:3` weights.

Because every registered regime has one held-out trace, this equals the mean
of the seven trace contrasts, but the evidence must retain both scope means
and the explicit `4:3` reconstruction.  Traffic traces are nested repeated
measurements, not bootstrap units.

The resulting value is one parent observation.  Parent observations are never
pooled across graph models or node counts.  The three model-stratum means are
combined with exactly one-third weight each.

## Eight local confirmatory hierarchies

There is one local hierarchy for each of two endpoints by four sizes.  Each
contains five registered contrasts: one equal-family global contrast and four
named-family secondary contrasts.  The beneficial directions are positive
for normalized restricted no-path time and negative for failure risk.

Each hierarchy uses the frozen bootstrap plan:

- 20,000 resamples;
- root seed `2026081003`;
- confidence level `159/160`;
- five multiplicity-adjusted intervals;
- two-sided empirical tail `1/1600`.

For every bootstrap replicate, parents are resampled independently within ER,
Barabasi-Albert and fixed-count SBM, then averaged within stratum, and finally
the three stratum means are averaged equally.  The same resample-index schedule
is used across the five contrasts in a hierarchy and across the two phases;
phase independence comes from the disjoint parent and traffic seed families,
not from changing the registered bootstrap root.

Because the same root, model-stratum IDs and parent counts are used, the exact
parent-index schedule is also shared across all eight hierarchies.  This is a
deterministic schedule choice, not outcome pooling.

Multiplicity is controlled separately within each phase: each phase contains
one 40-contrast studywise 95% family.  The 80 intervals across both phases are
not claimed to form one joint 95% simultaneous family.  Reusing the registered
index schedule across phases and the cross-phase replication state machine
below are conservative decisions added by this amendment, not fields of the
earlier precision artifact.

The four secondary contrasts are confirmatory in a phase only when that
phase's global interval is beneficial.  Otherwise they are reported as
descriptive even if their own intervals exclude zero.

## Independent confirmation rule

Formal and confirmation intervals and hierarchy gates are computed and
reported separately.  A contrast can be labelled independently confirmed only
when:

1. its formal adjusted interval is beneficial;
2. its confirmation adjusted interval is beneficial; and
3. for a secondary contrast, the global gate is open in both phases.

Pooling the two phases or meta-analysing them is exploratory and cannot rescue
a failed registered phase.  Estimates, interval widths and sign agreement for
all 40 contrasts are reported regardless of confirmation status.

For each phase and contrast, `interval_direction` is exactly one of
`beneficial` (the entire adjusted interval lies beyond zero in the registered
beneficial direction), `harmful` (the entire interval lies beyond zero in the
opposite direction), or `inconclusive` (all other cases).  `point_direction`
is `beneficial`, `harmful`, or `zero`.  Cross-phase `point_sign_agreement` is
`same_beneficial`, `same_harmful`, `one_or_both_zero`, or `opposite`.

Global contrasts have gate state `not_applicable`.  A secondary has gate state
`open` exactly when its own phase's global interval is beneficial, otherwise
`closed`.  Phase success requires a beneficial interval and an open or
not-applicable gate.  The cross-phase replication state is exactly one of
`independently_confirmed`, `formal_only`, `confirmation_only`, or `neither`,
according to the two phase-success Booleans.

## Censoring and sensitivity outputs

The registered lower quantile is `q=0.10`.  This amendment reports only its
identifiability and event coverage, by phase/size/model/family/scope/parent,
using the calibration rule: source and every named binary arm must each have
an observed-event fraction of at least `0.10` within that parent.  A cell is
identified only when every parent passes for the source and all binary arms.
No numerical censored quantile is estimated or reported.

Demand-aware results retain whether topology search changed the seed topology.
The primary analysis includes all registered parents.  A descriptive table
separates changed and unchanged parents for both primary endpoints.  Within
each exact phase/size/model/status group it reports parent count, canonical
parent values, arithmetic mean, minimum and maximum.  Empty groups report
count zero and null summaries; singleton groups report their value and mean
but no variance or interval.  An equal-model descriptive mean is reported only
when all three model strata are nonempty; otherwise it is null with status
`not_aggregated_missing_stratum`.  No subgroup bootstrap, p value, confidence
interval or confirmatory label is permitted.

## Evidence artifacts and fail-closed replay

The phase evidence schema is `formal-phase-inference-evidence.v1` and has the
following exact top-level fields:

`schema_version`, `status`, `phase`, `study_id`, `source_fingerprints`,
`analysis_revision`, `analysis_contract`, `block_registry`, `trace_contrasts`,
`parent_contrasts`, `hierarchies`, `event_coverage`, `activity_sensitivity`,
`limitations`, and `evidence_fingerprint`.

`status` must be `complete-strict-replay`.  Arrays follow canonical registered
orders; JSON object key order has no semantic meaning.  The artifact contains:

- all source fingerprints and the analysis-code revision;
- exact block and parent counts by size/model;
- trace-level contrasts and binary-arm counts;
- scope means, `4:3` parent reconstructions and model-stratum parent samples;
- point estimates, exact `tail_probability`, interval endpoints, hierarchy
  decisions and stratum parent counts for all 40 contrasts;
- event-coverage and demand-aware activity sensitivity tables;
- a canonical SHA-256 fingerprint over every preceding field.

All 20,000 exact bootstrap values for each contrast are stored inline as
canonical `[numerator, denominator]` pairs; there is no optional detached
payload or encoding choice in v1.  A strict loader rebuilds the entire evidence
object from manifests, summaries, artifacts and precision inputs and rejects
missing, extra, wrongly ordered semantic arrays, or altered content even when
an attacker recomputes the outer hash.

After both phase artifacts exist, schema
`formal-replication-evidence.v1` binds their fingerprints and contains exactly
`schema_version`, `status`, `formal_evidence_fingerprint`,
`confirmation_evidence_fingerprint`, `analysis_revision`, `contrast_results`,
`limitations`, and `replication_fingerprint`.  `status` is
`complete-strict-replay`.
`contrast_results` is the canonical 40-item registry and applies only the
enumerated direction, gate, success, sign-agreement and replication states
above.  The public builder accepts paths for and internally strict-loads both
complete raw phase source chains; loose in-memory source mappings and a
self-hashed phase JSON are insufficient.  It requires
the same calibration, precision, analysis revision and analysis contract,
while manifest, ledger, summary, block-artifact, paired-manifest and phase
evidence fingerprint sets must be disjoint.  It cannot change either phase
interval or gate decision.

Both phase and replication generators write only below `results/inference`.
They reject targets equal to any input or inside an execution output root, and
an existing target is accepted only when it is JSON-semantically identical to
the newly replayed mapping.  The analysis revision binds this tool, while all
tracked imports and the absence of untracked files below
`secondaryexploration` must match the execution revision declared by the
strict phase summaries.
