# Results writing support

This is an exact-arithmetic, descriptive projection of archived Source Data
for the [Results draft](../../results.md). It does not replace the canonical
evidence or perform new simulations, bootstrap resampling or hypothesis tests.

- [Evidence summary JSON](evidence-summary.json): 240 parent-stratum summaries,
  192 event-coverage cells, 32 activity groups and 416 descriptor cells across
  two phases. All source pointers and exact fractions are retained; original
  individual records remain in Source Data.
- [Readable complete support tables](descriptive-support.md): all parent-model
  means, coverage counts, activity groups and the ranges of all 13 descriptors
  across the 16 registered size-by-family cells in each phase.
- [Hashes](manifest.json): Source Data, generator and generated support files.
- [Claim–evidence map and statistical boundaries](../../results-writing-notes.md).

Reproduce from the repository root:

```powershell
python -m tools.build_results_writing_support
python -m unittest tests.test_results_writing_support -v
```

The script verifies the archived Source Data byte hash and primary registry,
then recomputes descriptive group means and measured block-duration sums with
exact rational arithmetic. The tests additionally reconstruct all primary
estimates from model means, recompute quantile-identification coverage from
event counts, verify changed/unchanged group partitions and preserve nulls,
check complete descriptor coverage, and compare numerical Results claims.
No derived cell is an additional independent experimental replicate.

The original Source Data remains at
[source-data.json](../../../results/source-data/synthetic-hypergraph-payment-v1/source-data.json).
Generation code and byte-bound outputs have fixed Git line-ending rules.
