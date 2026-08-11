# Secondary Exploration

Research repository for the second paper in the hypergraph payment-network
program.

**Working title**

> From Liquidity Depletion to Path Unavailability: Service-Reliability-Aware
> Topology Design for Hypergraph Payment Networks

The project is deliberately isolated from the first-paper repository. The
first-paper workspace may be consulted as a read-only source, but all new code,
experiment manifests, results, and manuscript material for paper 2 belong
here.

The authoritative approved-design draft is:

- [Paper 2 research and system design](docs/superpowers/specs/2026-07-31-secondaryexploration-design.md)
- [First implementation slice](docs/superpowers/plans/2026-07-31-project-scaffold-config-rng.md)
- [Hypergraph state-engine contract](docs/plans/2026-07-31-hypergraph-state-engine.md)
- [Full feasible-router contract](docs/plans/2026-07-31-full-feasible-router.md)
- [Core request-clock and service-event contract](docs/plans/2026-07-31-core-request-clock.md)
- [Deterministic topology-anchor contract](docs/plans/2026-07-31-deterministic-topology-anchors.md)
- [Parent-graph, NCH, and FHS contract](docs/plans/2026-07-31-parent-graph-nch-fhs.md)
- [Matched random parent-ensemble contract](docs/plans/2026-07-31-random-parent-ensembles.md)
- [Binary incidence-budget matching contract](docs/plans/2026-08-01-binary-incidence-matching.md)
- [IID traffic and request-trace contract](docs/plans/2026-08-01-iid-traffic-traces.md)
- [Paired experiment-runner contract](docs/plans/2026-08-01-paired-experiment-runner.md)
- [Survival and cost-metric contract](docs/plans/2026-08-01-survival-and-cost-metrics.md)
- [Parent-level hierarchical-inference contract](docs/plans/2026-08-01-hierarchical-inference.md)
- [Gate V1 prior-paper reproduction contract](docs/plans/2026-08-01-gate-v1-prior-paper-reproduction.md)
- [Gate V1 source and semantic evidence](docs/evidence/2026-08-01-gate-v1-source-and-semantic-audit.md)
- [Gate V1 independent audit](docs/reviews/2026-08-01-gate-v1-prior-paper-independent-audit.md)
- [Demand-aware objective contract](docs/plans/2026-08-01-demand-aware-objective.md)
- [Demand-aware objective independent audit](docs/reviews/2026-08-01-demand-aware-objective-independent-audit.md)
- [Demand-aware constructor contract](docs/plans/2026-08-01-demand-aware-constructor.md)
- [Demand-aware constructor independent audit](docs/reviews/2026-08-01-demand-aware-constructor-independent-audit.md)
- [Common capacity optimizer contract](docs/plans/2026-08-01-common-capacity-optimizer.md)
- [Common capacity optimizer independent audit](docs/reviews/2026-08-03-common-capacity-optimizer-independent-audit.md)
- [Study manifest and train-once pipeline contract](docs/plans/2026-08-03-study-design-manifest.md)
- [Study manifest and pipeline independent audit](docs/reviews/2026-08-03-study-pipeline-independent-audit.md)
- [Resumable pilot-artifact runner contract](docs/plans/2026-08-03-resumable-pilot-artifacts.md)
- [Resumable pilot-artifact runner independent audit](docs/reviews/2026-08-03-resumable-pilot-artifacts-independent-audit.md)

The result-free working manuscript materials are:

- [Manuscript workspace and drafting status](manuscript/README.md)
- [Methods working draft](manuscript/methods.md)
- [Canonical terminology ledger](manuscript/terminology.md)
- [Data Availability working draft](manuscript/data-availability.md)
- [Lightning source rights and redistribution audit](docs/evidence/2026-08-09-lightning-source-rights-audit.md)

## Current implementation status

The repository currently provides the reproducibility foundation, an
immutable hypergraph balance/state engine, complete balance-aware feasible
path search with exact tie-breaking, and a finite core request-clock simulator.
The simulator records explicitly censored `tau_dep`, `tau_nopath`, and
`tau_rej` events while continuing after failures to measure recovery, failure
episodes, and cumulative success. Deterministic `k`-uniform overlap-chain,
common-core sunflower, and binary path/star anchors now provide audited exact
resource counts and equal-per-node-capital states. Canonical simple parent
graphs now feed audited direct-binary, clique-expansion, closed-neighborhood
NCH, and bounded-BFS FHS transformations. Audited fixed-edge ER, frozen
star-initialized BA, and fixed-count SBM generators now produce connected
parent ensembles with exact shared node, edge, and mean-degree resources plus
replayable rejection metadata. A parent-preserving binary selector now creates
audited exact matches for feasible even incidence budgets and explicitly
bracketed `-1/+1` sensitivity baselines for odd budgets. Audited integer-weight
uniform, community-local, exogenous-hotspot, and
directional-drift kernels now generate replay-attested iid request traces with
independent endpoint and amount streams. A fingerprinted immutable paired-run
manifest now enforces common nodes, exact topology/state structure, equal
per-node initial capital, and reuse of the same request objects across every
variant. Request-indexed extensible pseudorandom route quantiles prevent
topology-dependent tie consumption from desynchronizing common random numbers,
and paired results are rejected unless their exact selected routes replay from
the manifest. The design records the finite 64-bit seed-family limitation
instead of claiming literal infinite-entropy uniformity. Exact discrete-time
Kaplan-Meier curves, fixed-horizon risks, censored quantiles, RMST, normalized
within-block service contrasts, and component-wise topology/route cost
witnesses are now independently audited. Parent-level aggregation and
request-index-stable cluster bootstrap now produce replay-validated exact
point estimates and Bonferroni percentile intervals while keeping exploratory
contrasts outside the confirmatory family. The executable global gate prevents
secondary or exploratory results from being promoted improperly. No formal
paper-2 confirmatory result or scientific claim has been implemented yet.
Verification Gate V1 has passed independent audit for its hash-attested
reproduction of the uploaded HPN paper's public 2022 input: the exact LN
node/edge/cost anchors and the principal NCH/FHS success/path-length directions
are recovered on the full 10,000-request trace. An independent numerical audit
reproduced every tracked trajectory and balance hash. The comparison result now
binds the topology, initial state, and request trace by fingerprint and has an
explicit full-replay validator. The anchor-matching graph filter's difference
from the public dependency, along with the success-level, NCH maximum-arity,
and large-FHS-tail differences, remains explicit in the discrepancy ledger.
Adversarial review of the v2 structurally framed fingerprints and full-replay
validator found no remaining blocker.

The demand-aware HPN stage now has an independently audited, exact four-term
training objective and feasible-set validator. Amount-weighted training demand,
all rational coefficients, parent identity, incidence budget, maximum arity,
and topology identity are fingerprint-bound; held-out service outcomes are not
inputs to this objective. Its independently audited deterministic constructor
enumerates exhaustive parent-connected candidates on small graphs and uses a
declared bounded candidate heuristic on formal-size graphs. Exact equal-
incidence moves can change memberships, arity distribution, and hyperedge
count; complete replay binds the seed, candidate pool, common search plan,
proposal stream, accepted steps, and final score. An independently audited
common capacity optimizer now preserves every node's integer capital while
applying the same load/risk initializer, robust regime-level lower-quantile
objective, unbiased proposal tickets, projected coordinate rule, and exact
evaluation budget to every topology. The uniform allocation remains an explicit
baseline, and complete replay binds every training scenario, proposal, score,
and accepted step. A strict phase-separated study manifest and semantic seed
ledger now freeze the synthetic pilot inputs, four training regimes, seven
held-out regimes, topology families, resource budgets, and routing seeds. The
audited train-once parent-block pipeline constructs NCH, FHS3, FHS5, and
demand-aware sources; deduplicates incidence-matched binary service baselines;
keeps clique expansions cost-only; applies one common capacity protocol; and
then evaluates all held-out traces with paired request objects and routing
tickets. Independent attacks confirmed that changing a held-out distribution
changes held-out results but leaves every trained object unchanged. The
calibration pilot is complete and independently audited. Its 18 exact
parent-model blocks feed a replayed calibration evidence artifact whose
parent-stratified censoring gate keeps the registered restricted-time and
fixed-horizon-risk route primary; lower-quantile inference opens only in the
two fully identified size-60 SBM/FHS3 cells. The recommended-A precision
freeze requires 20 independent parents per model, size, and phase. Distinct
formal and confirmation manifests now bind those counts, disjoint phase seeds,
the audited calibration basis, the frozen execution revision, and the pinned
CPython environment.

The pilot execution layer now has an independently audited resumable runner.
Each block is exactly replay-validated before an atomic checkpoint is exposed;
its compact scientific summary is cross-derived from a complete canonical
result witness rather than trusted independently. Resume rejects corrupt or
mixed manifest, ledger, parent, model, revision, and runtime identities. A
canonical progress summary derives its legal block registry internally and can
report `complete` only after every registered parent/model block is present.

The large-size runtime launch gate is also complete. One witnessed concurrent
batch measured every size-120/240 model stratum, including complete exact
replay for ER, and retained its raw stdout/stderr hash chain for strict
third-party reconstruction. Size-240 ER generation completed below the frozen
190-minute ceiling, and the single-block measurements support at most six
concurrent singleton processes. They do not authorize long-lived processes to
retain many replayed artifacts.

The original six workers were first interrupted by a system-initiated
shutdown after 78 blocks had been atomically published. The exact 60-block
historical checkpoint replayed successfully, six unpublished stale locks were
identity-checked and removed, and the frozen shards resumed under a fresh log
namespace. The first
[recovery evidence](docs/evidence/2026-08-10-formal-restart-recovery.md)
records this process without reading scientific endpoints. A second shutdown
left 166 valid blocks. Strict replay then exposed a cumulative-memory defect:
each long-lived shard retained all previously loaded artifacts. The frozen
scientific runner and all 166 artifacts remain unchanged, but formal execution
now proceeds through an independently audited
[bounded singleton scheduler](docs/plans/2026-08-11-formal-memory-operational-amendment.md):
240 logical one-block shards, at most six live children, a global lease,
per-batch memory and provenance gates, and exact final registry replay. The
[second recovery record](docs/evidence/2026-08-11-formal-memory-recovery.md)
documents the correction.

Legacy whole-phase finalization and inference are prohibited because they
retain all 240 complete artifacts. Their replacement is the separately
revision-bound
[streaming finalization and inference amendment](docs/plans/2026-08-11-formal-streaming-finalization-inference-amendment.md),
which strictly replays one artifact at a time while preserving the existing v1
summary, estimands, bootstrap, multiplicity, and confirmation contracts.
Confirmation execution and inferential analysis remain gated on complete
formal execution and audited streaming finalization.

Mechanism-adjacent interpretation is separately gated by the result-blind
[descriptive topology, balance and cost projection](docs/plans/2026-08-11-formal-descriptive-mechanism-projection.md).
It emits all 13 frozen source-versus-resource-matched-binary descriptors in
canonical order, streams one raw artifact at a time, keeps parent-model strata
separate, and intentionally provides no interval, p value, causal claim or
confirmatory success state.

The result-blind
[Results reporting contract](docs/plans/2026-08-11-results-reporting-contract.md)
precommits the complete source-data registry, two main result figures, one
global table and eight evidence-gated paragraph jobs. It prohibits selective
row omission, phase pooling, significance-only labels and numerical reporting
from manually copied values.

The package supports Python 3.10 or later and has no third-party runtime or
test dependency. Run the complete test suite from the repository root with:

```powershell
python -m unittest discover -s tests -v
```

## Reproducibility contract

The tracked smoke configuration is
[`configs/pilot/scaffold-smoke.json`](configs/pilot/scaffold-smoke.json). The
loader rejects missing or unknown fields, duplicate JSON keys, unsafe output
paths, invalid numeric ranges, and non-UTF-8 input. Its fingerprint is the
SHA-256 digest of canonical JSON, so a scientifically relevant configuration
change creates a different experiment identity.

The tracked study-pipeline pilot is
[`configs/pilot/synthetic-pipeline-v1.json`](configs/pilot/synthetic-pipeline-v1.json).
Its strict schema freezes all result-independent scientific controls and
rejects unknown result fields, invalid phase provenance, incomplete traffic
registries, or parent resampling ceilings unsupported by the generator.

Stochastic components derive independent 64-bit seeds from the tuple
`(base_seed, namespace, index)` using the versioned SHA-256 framing rule in
`secondaryexploration/randomness.py`. Reusing the same tuple replays the same
standard-library random sequence; components must use distinct semantic
namespaces such as `topology` and `traffic`.
