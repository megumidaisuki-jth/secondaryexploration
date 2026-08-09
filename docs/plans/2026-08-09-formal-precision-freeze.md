# Formal precision freeze: recommended A

## Decision

The user authorized the recommended option to be adopted after one minute
without a reply. Recommended A therefore freezes a smallest effect of
scientific interest of 0.10 for both normalized restricted `tau_nopath` and
absolute fixed-horizon failure-risk difference. The target simultaneous
half-width is 0.05 for each global hypergraph-versus-binary contrast and 0.10
for each named topology-family contrast.

## Multiplicity and hierarchy

There are eight local hierarchies: two endpoints by four primary node sizes.
Each contains one global contrast and four secondary family contrasts, for 40
confirmatory intervals in total. Studywise confidence is 95%. Allocating
alpha equally across the eight local hierarchies gives local confidence
159/160; Bonferroni adjustment across each hierarchy's five intervals then
gives the same two-sided empirical tail probability, 1/1600, as a direct
40-contrast adjustment. This preserves one global gate per executable
hierarchy while controlling the complete registered family.

Twenty thousand stratified parent-bootstrap resamples put 12.5 expected
replicates in each adjusted tail. Parent IDs are resampled independently
within ER-GNM, Barabasi-Albert and fixed-count SBM strata, and the three
resampled stratum means receive equal weight.

The 12-requests-per-node administrative horizon is retained. Formal,
confirmation and bootstrap roots are respectively 2026081001, 2026081002 and
2026081003, so outcome generation, independent confirmation and resampling use
disjoint deterministic seed families.

## Planning calculation

Calibration traces are first averaged within each parent. The four
same-distribution and three shifted regimes receive weights 4:3, matching
their registered trace counts. Global contrasts average the four topology
families equally. For a candidate count `n` per model stratum, the planning
variance is

`(s_ER^2 + s_BA^2 + s_SBM^2) / (9 n)`.

Using the 1/1600 upper-tail normal critical value, the worst raw requirement
is 19 parents per model for global intervals and 12 for secondary intervals.
The design rounds upward to 20 parents per model and size. This is applied to
sizes 120 and 240 conservatively because calibration directly estimates
dispersion only at sizes 30 and 60.

The normal calculation is used only to choose simulation count. Formal
inference remains the registered stratified parent bootstrap; the pilot does
not establish achieved power or finite-sample coverage.

## Runtime gate

Each formal or confirmation phase contains 240 parent-model blocks. The
calibration envelope projects about 1,792,607 sequential seconds (498 hours)
per phase. Formal and confirmation phases use disjoint seed families. Neither
may launch until the size-120/240 execution path is profiled and a verified
parallel resource envelope is recorded.
