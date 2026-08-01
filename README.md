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
proposal stream, accepted steps, and final score. The common capacity optimizer
is the next implementation slice.

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

Stochastic components derive independent 64-bit seeds from the tuple
`(base_seed, namespace, index)` using the versioned SHA-256 framing rule in
`secondaryexploration/randomness.py`. Reusing the same tuple replays the same
standard-library random sequence; components must use distinct semantic
namespaces such as `topology` and `traffic`.
