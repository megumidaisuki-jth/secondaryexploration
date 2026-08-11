# Result-blind descriptive topology, balance and cost projection

## Timing and status

This contract was frozen on 2026-08-11 while formal execution contained 166
complete parent-model artifacts and two missing size-120 BA blocks were still
running. No formal endpoint value, parent contrast, interval, hierarchy state
or phase comparison was read, aggregated or summarized to choose these
metrics. Pilot artifacts were used only to verify the already documented
result-witness field layout.

The projection is exploratory and descriptive. It is not a ninth hierarchy,
does not modify the 40 registered intervals in either phase, has no confidence
interval, p value, multiplicity allocation, gate or success state, and cannot
rescue a failed formal or confirmation contrast. Formal and confirmation
projections remain separate.

## Source and revision boundary

- Scientific block execution remains frozen at
  `425710a418b1b28e6c5cd813dff18aeeaa6303c3`.
- The v1 streaming finalizer and primary inference route remain frozen at
  analysis revision `9ecaadec84f8bebe799fb507969de8e0a0947b66`.
- This projection is implemented by a separate tool and binds its own committed
  `projection_revision`.
- A phase can enter this projection only after its exact 240-block
  `synthetic-study-run-summary.v1` has passed complete streaming replay.
- Every block is strict-loaded one at a time; the tool retains derived exact
  fractions and provenance only, then releases the full artifact.
- Each held-out simulation is re-executed from its witnessed initial state,
  requests and registered per-request route-choice seed family. Its complete
  canonical route, shortest-hop, bottleneck, tied-route, depletion, final-state
  and event payload must equal the raw witness before any descriptor is used.
- Every source panel is reconstructed under the frozen resource-matching
  contract: binary arms are unique, genuinely binary, incidence-exact or the
  registered ordered adjacent bracket, and collectively cover the canonical
  variant registry without changing within-panel weights.

## Fixed metric registry

All metrics are source-family minus the exact mean of only the binary arm or
arms registered to that source family. No binary arm is pooled across panels.

### Static metrics, one value per parent topology

1. `topology_pair_coverage_fraction`: unordered node pairs co-contained in at
   least one hyperedge divided by `choose(n,2)`.
2. `topology_mean_pair_multiplicity_covered`: total hyperedge co-membership
   multiplicity divided by the number of covered unordered pairs.
3. `initial_coordinate_imbalance`: across all incidence coordinates, the mean
   absolute deviation of each within-hyperedge balance share from equal share,
   `mean_(e,v) |x_(e,v)/sum_u x_(e,u) - 1/|e||`.

The initial state must be byte-semantically identical across the seven held-out
traces for a variant; otherwise projection fails.

### Dynamic metrics, first computed per held-out trace

4. `final_coordinate_imbalance`: the same incidence-weighted balance-share
   deviation in the final state.
5. `final_zero_coordinate_fraction`: zero final directional-balance
   coordinates divided by incidence count.
6. `optimal_route_multiplicity_mass_per_attempt`: sum of the exact router's
   `tied_route_count` over all requests divided by the fixed horizon; no-path
   requests contribute zero.
7. `multiple_optimal_route_fraction_per_attempt`: requests with
   `tied_route_count > 1` divided by the fixed horizon.
8. `route_bottleneck_mass_per_attempt`: sum of selected-route bottleneck
   fractions divided by the fixed horizon; no-path requests contribute zero.
9. `route_hop_mass_per_attempt`: sum of selected-route shortest-hop counts
   divided by the fixed horizon; no-path requests contribute zero.
10. `traversed_hyperedge_count_per_attempt`.
11. `signaled_participant_slots_per_attempt`.
12. `quadratic_coordination_exposure_per_attempt`.
13. `unique_signaled_participants_per_attempt`.

Items 10--13 divide the serialized exact dynamic-cost total by the common
trace horizon. They are not conditional on acceptance, so no missing-value
rule or post-result denominator choice is introduced.

## Frozen aggregation

For each dynamic metric, source-family, parent and phase:

1. compute the paired source-minus-registered-binary contrast separately on
   each of the seven immutable held-out traces;
2. average the four same-distribution traces and the three shifted traces
   separately;
3. combine those two means with the existing frozen `4:3` weights.

Static contrasts are computed once per parent. ER-GNM, BA and fixed-count SBM
remain separate strata. For each size, source family and metric, the evidence
retains the 20 exact parent values, mean, minimum and maximum within each model
stratum, followed by the equal mean of the three stratum means. No variance,
standard error, interval, p value, trend test or cross-phase pooled value is
emitted.

## Interpretation boundary

The projection can test whether a service-reliability pattern is descriptively
consistent with registered topology, residual-balance or coordination
features. It cannot identify a mechanism or establish causality. In particular:

- topology pair coverage and optimal-route multiplicity are bounded redundancy
  descriptors, not guarantees of usable alternative routes;
- balance-share deviation and zero-coordinate fraction describe state
  dispersion, not an independent failure endpoint;
- route bottleneck and hop masses mix route availability with route properties;
- coordination metrics quantify declared protocol work only and are not fees,
  latency, privacy leakage or implementation throughput;
- selecting or highlighting a metric after reading endpoint results is
  prohibited; all 13 metrics must be emitted in canonical order.

## Phase-complete invocation

Only after a phase has a strict complete run summary, invoke the committed
tool with its own 40-hex revision. For the formal phase the canonical command
shape is:

```powershell
python tools/formal_descriptive_projection.py `
  configs/formal/synthetic-formal-v1.json `
  outputs/formal/synthetic-formal-v1/run-summary.json `
  configs/pilot/synthetic-calibration-v1.json `
  results/pilot/synthetic-calibration-v1/evidence.json `
  results/planning/formal-precision-v1.json `
  --projection-revision <committed-projection-revision> `
  --output results/inference/formal-descriptive-mechanism-v1.json
```

The confirmation invocation substitutes the confirmation manifest, run
summary and output name. The writer permits only a new or byte-semantically
identical target below `results/inference`; a trusted later load must use the
complete raw-source replay loader rather than the structural validator alone.

## Publication gate

Discussion may use these metrics only after the relevant phase projection has
passed complete raw-source replay and the statement is labelled exploratory.
No metric may be described as a mediator, cause, mechanism proof, robustness
test or confirmatory result. The 2026 Lightning panel remains outside this
synthetic projection and outside the confirmatory bootstrap.
