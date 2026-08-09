# Formal and confirmation inference artifact contract

## Purpose and launch boundary

This contract defines the only route from the completed synthetic formal and
independent-confirmation phases to confirmatory claims.  It is frozen while
the formal workers are running, but the implementation is deliberately added
only after both execution summaries have been strictly finalized.  This
preserves the execution-code snapshot bound to revision
`425710a418b1b28e6c5cd813dff18aeeaa6303c3`.

No partial run summary, loose block JSON, or manually assembled table is an
analysis input.  A phase can be analysed only after the runner has rebuilt a
`status=complete` summary from all 240 registered block artifacts.

## Strict inputs

For each phase, the evidence generator must strictly replay all of:

1. the phase manifest and exact study seed ledger;
2. the complete 240-block run summary;
3. every block through the hash-attested artifact loader under the summary's
   declared execution revision and environment;
4. the audited calibration evidence and recommended-A precision artifact;
5. the exact registered block-key set: four sizes, twenty parents per size,
   and the three separately named parent-model strata.

Formal and confirmation evidence remain separate.  Their manifest, ledger,
summary, block-artifact and evidence fingerprints must be disjoint.

## Trace-level primary contrasts

For each held-out trace and each source family (`demand-aware`, `fhs3`,
`fhs5`, `nch`), the reference arm is the exact equal mean of every registered
binary-matched variant in that same paired trace.  Binary variants are never
promoted to independent observations.

For horizon `H`, source value `S`, and binary-arm values `B_j`, the two primary
source-minus-reference contrasts are:

- normalized restricted no-path time:
  `S.tau_nopath / H - mean_j(B_j.tau_nopath / H)`;
- fixed-horizon failure risk:
  `I(S.tau_nopath observed) - mean_j I(B_j.tau_nopath observed)`.

The global trace contrast is the equal mean of the four source-family trace
contrasts.  Thus the global endpoint is not weighted by the number of source
or binary variants.

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

## Censoring and sensitivity outputs

The lower `tau_nopath` quantile remains exploratory and explicitly censored;
it is not substituted for either primary endpoint.  Evidence additionally
reports, by phase/size/model/family/scope, source and each binary arm's event
coverage.

Demand-aware results retain whether topology search changed the seed topology.
The primary analysis includes all registered parents.  A labelled sensitivity
table separates changed and unchanged parents without treating either subset
as a replacement confirmatory sample.

## Evidence artifacts and fail-closed replay

The phase evidence artifact must contain:

- all source fingerprints and the analysis-code revision;
- exact block and parent counts by size/model;
- trace-level contrasts and binary-arm counts;
- scope means, `4:3` parent reconstructions and model-stratum parent samples;
- point estimates, bootstrap tails, interval endpoints, hierarchy decisions
  and stratum parent counts for all 40 contrasts;
- event-coverage and demand-aware activity sensitivity tables;
- a canonical SHA-256 fingerprint over every preceding field.

The bootstrap value vectors may be stored in a separate hash-attested payload
to control JSON size, but interval replay must reproduce them exactly.  A
strict loader rebuilds the entire evidence object from manifests, summaries,
artifacts and precision inputs and rejects missing, extra, reordered or
semantically altered content even when an attacker recomputes the outer hash.

After both phase artifacts exist, a small replication artifact binds their
fingerprints and deterministically applies the independent-confirmation rule.
It has no path to raw loose JSON and cannot change either phase's interval or
gate decision.
