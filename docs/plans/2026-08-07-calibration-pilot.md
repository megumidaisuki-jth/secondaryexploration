# Horizon, search-coverage, and parent-variance calibration pilot

## Decision status

This is a new pilot phase with a disjoint root seed. It does not alter or pool
the completed `synthetic-pipeline-pilot-v1` outputs and cannot be relabelled as
formal evidence.

## Why a second pilot is required

The first pilot contains three independent parent-graph instances per size
(one ER, one BA, and one SBM). Its 168 panel-trace observations are nested
traffic subsamples, not 168 independent topology replicates. All hypergraph
`tau_nopath` outcomes are administratively right-censored at four requests per
node, so a finite 10% lower quantile cannot be identified. The demand-aware
search changed its FHS5 seed in only one of six blocks.

These facts preclude a defensible formal sample-size freeze. In particular,
the observed traffic traces cannot be substituted for independent parent
graphs when estimating uncertainty.

## Frozen calibration changes

Relative to `configs/pilot/synthetic-pipeline-v1.json`, the new manifest changes
only:

- study identity, output root, and disjoint base seed;
- parent replicates from 1 to 3 per model-size cell;
- requests per node from 4 to 12; and
- topology proposal budget from 120 to 5,000.

The run therefore has 18 independent parent-graph blocks: two sizes, three
models, and three parent replicates. Seven held-out regimes remain nested
within every parent. Training/test separation, request pairing, resource
matching, topology families, capacity search, and all traffic distributions
remain unchanged.

Three parent replicates are a calibration choice, not a powered formal sample
size. They provide three independent instances within each model-size stratum
for preliminary dispersion and runtime estimation. ER, BA, and SBM remain
distinct structural strata: their nine graphs at one size are never pooled as
nine identically distributed observations for a single variance estimate.

## Result-independent rationale

The 12-request-per-node horizon is exactly three times the first pilot horizon.
It is fixed before observing any continuation outcome. The 5,000-proposal
budget is based only on deterministic training-topology coverage diagnostics:
the completed parents changed in 1/6 blocks at 120 proposals, 3/6 at 1,000,
and 4/6 at 5,000. No held-out service outcome was consulted when choosing the
search budget.

The diagnostic is frozen at
`results/pilot/synthetic-pipeline-v1/search-coverage.json` with fingerprint
`1baceb77d3f98afe9ee425f2e3b1fe9c3f111a9351abe886f5b7c96bcbf9c781`.
Its source-bound verifier regenerates parent graphs, training traces, demand,
and topology searches without constructing any held-out request trace.

## Required outputs

The calibration must run every registered block without optional stopping and
produce:

1. strict resumable block artifacts and a complete run summary;
2. parent-aware evidence using the same within-trace bracket, within-parent,
   and parent-equal aggregation contract;
3. source-event coverage and censoring by family, size, model, and traffic
   scope;
4. parent-level dispersion for normalized restricted `tau_nopath`, failure
   risk, success rate, accepted value, and component-wise cost;
5. demand-aware feasible/accepted search diagnostics; and
6. generation/validation wall-clock projections for sizes 120 and 240.

## Formal-freeze gate after calibration

The calibration does not itself choose formal `n`. A later precision artifact
must state the smallest effect of scientific interest, target simultaneous
interval half-width, confidence family, bootstrap resamples, independent unit,
and runtime envelope. If the finite lower quantile remains unidentified, the
formal design must either preregister a longer horizon or elevate RMST and
fixed-horizon failure risk while retaining the quantile as censored; horizon
values may not be imputed as failures.
