# Independent audit: parent-level hierarchical inference

Date: 2026-08-01

Scope: `secondaryexploration/metrics/inference.py`, its exports, plan, paired
observation factory, and focused tests.  The auditor did not implement the
feature and changed no files.

## Independent checks

- 120 unequal-trace-count synthetic data cells independently recomputed as
  trace means within parents followed by equal-weight means across parents;
- all 120 cells intentionally differed from the invalid pooled-trace mean;
- 13 grouping attacks covering mixed horizons, arms, metrics and analysis
  cells, repeated traces, repeated manifest fingerprints within and across
  parents, duplicate parents, noncanonical ordering, and invalid cell IDs;
- exact independent reconstruction of the SHA-256 seed framing and rejection
  `randbelow` for 524 bootstrap replicates at parent counts 2, 3, 5 and 8;
- four bootstrap-prefix checks showing that increasing registered `B` does not
  change earlier replicates;
- 274 bootstrap means for two contrasts, all identical to an independently
  calculated exact-`Fraction` oracle and all using common parent indices;
- five cross-contrast alignment attacks covering analysis cell, horizon,
  missing traces, trace-ID layout and manifest-fingerprint layout;
- six independently recomputed left-empirical-quantile interval endpoints;
- confirmatory `K=2` tails `alpha/(2K)=1/20` and exploratory nominal tails
  `alpha/2=1/10`, with exploration excluded from `K`;
- five forged public interval families altering indices, samples, estimates,
  bootstrap order or endpoints, all rejected by full replay; and
- positive-benefit and negative-benefit global successes plus a failed global
  gate, with secondary and exploratory labels correct in all three cases.

The auditor confirmed that the documentation labels the percentile cluster
bootstrap as an asymptotic approximation, not a finite-sample exact coverage
claim.

## Focused replay

```powershell
python -m unittest -v tests.unit.metrics.test_inference tests.unit.metrics.test_paired
```

The command passed 13 of 13 tests on Python 3.10.16 and bundled Python 3.12.13.

## Decision

**PASS.** No blocking or non-blocking implementation issue remained.
