# Calibration evidence and formal-precision freeze

**Status:** implementation contract; no formal sample size is frozen here.

## Statistical unit and hierarchy

The independent unit is one generated parent-graph instance within a fixed
`node_count × parent_model` cell. ER-GNM, Barabasi-Albert, and fixed-count SBM
are structural strata, not exchangeable replicates. Held-out traffic regimes,
hypergraph variants, and incidence-bracketing binary arms are paired or nested
measurements inside the same parent graph.

For every topology contrast, the evidence generator must:

1. average the one or two matched-binary arms within a trace;
2. form the hypergraph-minus-binary contrast within that trace;
3. average registered traces of the same scope within a parent graph; and
4. report dispersion across the three parent graphs only within the exact
   size/model/family/scope cell.

It must never report the 18 blocks as a single `n=18` sample, count the seven
traffic regimes as independent graphs, or use the number of routing requests
as inferential replication.

## Calibration outputs

The compact, source-bound artifact will contain:

- fixed-horizon source-event and censoring counts by size, model, topology
  family, and traffic scope;
- exact parent-level values, means, ranges, and unbiased sample variances for
  normalized restricted `tau_nopath`, fixed-horizon failure risk, success
  rate, accepted value, and every dynamic-cost component;
- demand-aware topology-change, feasible-evaluation, and accepted-step
  coverage;
- validated generation and replay-validation times; and
- per-block size-120 and size-240 runtime projections derived separately for
  each parent model from the observed 30-to-60 scaling ratio.

The three-parent variance estimates are explicitly preliminary. They are
planning inputs, not confirmatory intervals or evidence of superiority.

## Censoring gate

An administratively censored `tau_nopath` observation contributes follow-up
through the registered horizon and is never converted into an event at the
horizon. Quantile eligibility is checked separately for every parent graph and
for the source topology plus every matched-binary bracket arm; nested traffic
events are never pooled across parents to open this gate. A size/model/family/
scope cell is eligible only if all three parents satisfy both source and binary
checks. If calibration still does not identify the registered lower quantile,
the formal design must choose one of two preregistered routes before formal
simulation:

- extend the horizon using a new disjoint seed family; or
- make restricted mean/restricted time and fixed-horizon failure risk primary,
  while retaining the lower quantile as censored or exploratory.

The choice may use complete calibration results but cannot be changed after
formal outcomes are inspected.

## Precision freeze inputs

A later immutable precision artifact must supply all of the following:

- `AUTHOR_INPUT_NEEDED`: smallest effect of scientific interest for every
  confirmatory endpoint, in its reported units;
- `AUTHOR_INPUT_NEEDED`: target simultaneous interval half-width;
- familywise confidence level and the exact confirmatory family size;
- parent-bootstrap root seed and resample count satisfying the discrete tail
  constraint;
- planned parent count per size/model stratum;
- horizon and censoring endpoint choice; and
- the runtime envelope and independent confirmation allocation.

For planning only, a normal-approximation half-width calculation may combine
the exact calibration sample variance with the Bonferroni critical level. The
formal analysis remains the registered parent-cluster bootstrap; the planning
formula is not reported as achieved power or finite-sample coverage. The final
parent count is the maximum required across the prespecified confirmatory
cells, then rounded upward and checked against the runtime envelope.

No sample-size value may be invented when an effect or precision target is
missing. No run may continue until statistical significance is obtained.

## Reproducibility gate

The evidence writer must refuse an in-progress run summary, require the exact
frozen manifest fingerprint and exact 18 block-key set, strictly replay all 18
block artifacts, bind the compact artifact to the manifest, seed ledger,
code revision, runtime environment, run-summary fingerprint, and base pilot
evidence fingerprint, then write atomically. A corrupted or duplicate-key JSON
artifact must fail closed on load.
