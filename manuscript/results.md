# Results

## A. Complete execution and phase-separated inference

Both the formal and confirmation phases completed all 240 registered
parent-graph blocks, providing the full evidence set for the synthetic
benchmark ([Fig. 1](generated/synthetic-v1/figure-1-design.pdf)). At each
network size, each phase contained 20 independent parents from each of the
Barabási–Albert (BA), ER-GNM and fixed-count stochastic block model (SBM)
strata. Each contrast therefore used 60 independent parents. The four
same-distribution and three distribution-shift traces within a parent were
nested measurements, combined with the frozen 4:3 scope weights rather than
treated as additional independent replicates. Formal and confirmation used
separate phase data and were not pooled. Archived replay outputs and their
source bindings were checked before preparing the Results displays.

All comparisons used source-minus-resource-matched-binary contrasts. The
global contrast assigned equal weight to the four source families. Each
phase retained 40 contrasts in eight five-contrast hierarchies. The
multiplicity-adjusted percentile interval bounds used 20,000 stratified
parent-cluster bootstrap resamples, adjusted empirical probability 1/1600 in
each tail and local confidence parameter 159/160. The registered studywise
95% family applied separately within each phase, not jointly to the 80
cross-phase intervals. Exact estimates and bounds, gate states and source
identifiers are retained in [Source Data](../results/source-data/synthetic-hypergraph-payment-v1/source-data.json).

## B. Resource-matched service contrasts reproduced across phases

All eight global contrasts met the registered independent-confirmation
criterion: the adjusted interval lay in the beneficial direction in both
phases ([Fig. 2](generated/synthetic-v1/figure-2-global-contrasts.pdf);
[Table 1](generated/synthetic-v1/table-1.md)). At 30, 60, 120 and 240 nodes,
the formal fixed-horizon failure-risk differences were −0.425, −0.559,
−0.701 and −0.805; the corresponding confirmation differences were −0.449,
−0.575, −0.693 and −0.787. These are absolute probability differences, not
relative percentage reductions. For normalized restricted no-path time,
formal differences were 0.192, 0.307, 0.437 and 0.566, compared with 0.216,
0.305, 0.441 and 0.562 in confirmation. This endpoint expresses request-clock
time as a fraction of the administrative horizon, H=12 times the node count.
Table 1 reports both adjusted bounds for every estimate; inference was based
on exact fractions rather than rounded display values.

All phase-specific global gates were open. Each of the 32 named-family
contrasts also had a beneficial adjusted interval in both phases and thus
met the independent-confirmation criterion
([Fig. 3](generated/synthetic-v1/figure-3-replication-matrix.pdf)). This covered
demand-aware HPN, FHS3, FHS5 and NCH, both endpoints and all four sizes. No
record was classified as formal-only, confirmation-only or neither. These
comparisons were each against the family's own resource-matched binary
reference; they were not tests of one hypergraph family against another.
The [complete numerical registry](generated/synthetic-v1/numerical-registry.json)
retains every global and named-family result.

The descriptive parent-model means had the registered beneficial sign in
all three strata. For each phase, all 60 failure-risk cell means were
negative and all 60 normalized restricted no-path-time cell means were
positive, where a cell specifies source family (including the global
contrast), size and parent model. These were model-stratified descriptive
patterns, not additional independent tests or evidence of equal effects
between models. All 20 parent values per cell and the corresponding means
and ranges are available in the
[descriptive support](generated/results-writing-v1/descriptive-support.md).

## C. Censoring coverage and demand-aware activity

Lower-quantile identification was incomplete despite the phase-level
service contrasts. In each phase, only 2 of the 96 coverage cells met the
q=0.10 identification rule for every parent and every registered arm matched
to its source. These were the FHS3, fixed-count SBM, same-distribution cells
at 120 and 240 nodes. No parent met the joint source-and-matched-arms rule
in 34 formal cells and 24 confirmation cells. All remaining cells had
partial coverage. These counts describe cells, not independent trials:
the same parents recur across source families and traffic scopes. No
numerical q=0.10 stopping-time quantile was estimated, including in the
fully covered cells. The full 192-cell coverage registry is retained in the
descriptive support and Source Data.

Demand-aware training changed the seed topology for 33, 21, 5 and 1 of the
60 parents at increasing sizes in the formal phase, and for 34, 16, 13 and
1 parents in confirmation. At 240 nodes, the changed subgroup contained
one BA parent in formal and one ER-GNM parent in confirmation, with the
other two strata empty in each phase. Consequently, no equal-model changed
subgroup mean was available at that size for either endpoint. The
unchanged subgroup's failure-risk means were −0.922 and −0.898, and its
normalized restricted no-path-time means were 0.638 and 0.647, respectively.
All changed and unchanged cells, including empty and singleton strata, are
retained. These source-versus-binary subgroup summaries were descriptive,
with no subgroup intervals or p values; they did not isolate the effect of
changing the topology or establish a training benefit over the seed topology.

## D. Descriptive cost patterns and computational scope

The exploratory projection retained all 13 descriptors for every source
family, size and phase. In each phase, all 16 size-by-family equal-model
means showed higher pair coverage and covered-pair multiplicity, lower
initial and final coordinate imbalance, and a lower final zero-coordinate
fraction than the matched binary reference. Per-attempt route-hop mass,
traversed-hyperedge count and route-bottleneck mass were lower in all 16
cells, whereas signaled participant slots, unique signaled participants
and quadratic coordination exposure were higher. Quadratic coordination
exposure differences ranged from 6.857 to 316.591 in formal and from 6.886
to 306.536 in confirmation. The two optimal-route multiplicity descriptors
had mixed signs across cells. The complete descriptor registry, including
all model-stratum summaries, is provided in the
[machine-readable support](generated/results-writing-v1/evidence-summary.json).
These descriptive patterns co-occurred with the service contrasts but did
not identify a causal mechanism. The coordination descriptors were
protocol-defined counts or exposures, not measured latency or monetary cost.

Recorded generation durations summed to 294.922 block-hours in formal and
264.831 block-hours in confirmation; exact-validation durations summed to
340.418 and 299.433 block-hours, respectively. These totals sum measured
within-block elapsed durations and are neither end-to-end wall-clock times
nor CPU-hour measurements. They exclude later phase-inference and
descriptive-projection work and are not a parallel-speedup benchmark.
Both run summaries recorded CPython 3.12.13 on Windows AMD64; a whole-run
peak-memory measurement was not available in those summaries. The
conclusions are restricted to the registered synthetic parent ensembles,
traffic kernels, capacities, horizons and balance-aware routing protocol.
No Lightning structural panel was included in these Results or in the
synthetic bootstrap.
