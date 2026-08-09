# Stratified parent-cluster bootstrap

## Purpose

Formal synthetic inference must combine ER-GNM, Barabasi-Albert, and
fixed-count SBM evidence without pretending that the three graph-generating
models are identically distributed parent replicates.

## Estimator

For every registered contrast:

1. form paired trace contrasts;
2. average traces within each parent graph;
3. average parent graphs within each declared model stratum; and
4. give the three stratum means equal weight.

Thus parent count controls precision within a stratum, while a stratum with
more parents cannot silently dominate the estimand. Node size remains a
separate analysis cell unless the formal precision manifest explicitly
defines a higher-level size estimand.

## Resampling

Each bootstrap replicate resamples parent IDs with replacement independently
inside every model stratum. Seed namespaces include the stratum ID, so equal
parent counts do not create artificial identical resample vectors across
models. All registered contrasts reuse the same within-stratum parent indices,
preserving paired dependence and simultaneous-interval alignment.

The bootstrap statistic is the equal mean of the resampled stratum means.
Traffic traces are never resampled as independent parents. Percentile
intervals retain the existing exact-Fraction, Bonferroni-tail, hierarchy, and
resample-prefix contracts and remain asymptotic bootstrap approximations.

Every paper table and machine-readable export must report the parent count in
each named model stratum alongside the total parent count. The total is a
precision summary only; it must not be presented as evidence that parent
graphs were pooled or that strata with more parents received more estimand
weight.

## Fail-closed rules

- at least two model strata and at least two parents per stratum;
- canonical, unique stratum IDs and parent IDs;
- identical stratum layout across simultaneous contrasts;
- identical parent/trace/fingerprint layout within each corresponding stratum;
- one common higher-level analysis cell, metric horizon, and bootstrap plan;
- no duplicate manifest fingerprint across strata under a renamed parent; and
- sufficient bootstrap resamples to resolve every adjusted empirical tail.

## Verification

Tests must distinguish equal-stratum weighting from pooled-parent weighting,
independently reproduce stratum-specific index vectors, verify aligned
resamples across contrasts, reject mixed/missing stratum layouts, and exercise
confirmatory hierarchy gating in both beneficial directions.
