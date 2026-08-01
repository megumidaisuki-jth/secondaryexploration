# Secondary Exploration: Paper 2 Research and System Design

**Date:** 2026-07-31
**Status:** Approved research contract derived from the grilling session;
implementation began on 2026-07-31
**Repository:** `E:\second` / `megumidaisuki-jth/secondaryexploration`
**Target venue:** IEEE Transactions on Network and Service Management (TNSM)

## 1. Working title and paper argument

### Working title

**From Liquidity Depletion to Path Unavailability: Service-Reliability-Aware
Topology Design for Hypergraph Payment Networks**

Chinese working title:

**从流动性耗尽到路径不可用：面向服务可靠性的超图支付网络拓扑设计**

### One-sentence argument

Under matched capital and infrastructure budgets, hypergraph topology,
traffic demand, and balance-aware routing jointly determine how local
liquidity depletion propagates into end-to-end path unavailability; a
demand-aware topology design and paired evaluation framework will identify the
resulting cost-reliability regimes without assuming a universal topology
winner.

This is a planned argument. Result-dependent verbs such as *improves* or
*outperforms* are prohibited until held-out experiments support them.

## 2. Repository and publication boundary

This repository is the sole writable project for paper 2. The paper 1
repository at `E:\newblockchain` is read-only reference material.

Paper 1 owns:

- exogenous, balance-independent atomic routing;
- first directional-balance depletion, `tau_dep`;
- finite-state equations, capacity asymptotics, and high-order conditional
  depletion bounds;
- theoretical chain/star corollaries and a small depletion-to-service bridge.

Paper 2 owns:

- balance-aware feasible routing and request-clock simulation;
- first path unavailability, `tau_nopath`, and final rejection, `tau_rej`;
- resource-matched topology comparisons across binary and hypergraph PCNs;
- demand-aware hypergraph construction;
- recovery, rebalancing, and cost-reliability analysis;
- large synthetic ensembles and Lightning-topology cross-sections.

Definitions and public input data may be shared with attribution. Numerical
trajectories, result tables, random-seed families, experiment manifests, and
paper-specific claims must not be reused across the two papers.

## 3. Canonical terminology and events

| Canonical term | Definition |
|---|---|
| Hypergraph payment network (HPN) | A fixed finite hypergraph whose hyperedges are multi-party payment channels with conserved member balances. |
| Directional balance | `x[e,v]`, the balance contributed by participant `v` inside hyperedge `e`. |
| Request clock | The index of every attempted payment request, accepted or rejected. All service events use this clock. |
| `tau_dep` | First request index after an accepted payment at which any directional balance becomes exactly zero. |
| `tau_nopath` | First request index at which no globally feasible path exists for that request under the declared protocol constraints. |
| `tau_rej` | First request index at which the payment is finally rejected after the declared routing and retry policy. |
| Balance-aware routing | Routing that searches the current residual-balance state. |
| Demand-aware topology | A topology constructed from training demand under fixed capital, incidence, and arity constraints. |
| Incidence budget | `sum_e |e|`, used as a topology-construction resource measure. |
| RMST | Restricted mean survival time under a prespecified observation horizon. |

The request clock is one-based, with horizon `T` equal to the number of
attempted requests. An explicit observation flag distinguishes an event at
request `T` from right-censoring at `T`. To preserve the paper-1 boundary
convention, an initially zero directional balance sets `tau_dep=0`; otherwise
`tau_dep` can only be created by an accepted atomic payment that newly reaches
zero.

`tau_nopath` and `tau_rej` coincide only in the core experiment, where the
router has complete state information, searches the full feasible hypergraph,
and has no non-liquidity rejection cause. Sensitivity experiments must keep the
two events separate. Core recovery after first rejection is the first later
accepted request of any source-destination pair, so it measures restoration of
network service rather than necessarily restoration of the failed pair.

## 4. Core research questions

1. Under equal node count, per-node capital, incidence budget, and demand,
   which topology features change request-level service survival?
2. When does first local directional-balance depletion provide useful advance
   warning of path unavailability, and when can path unavailability occur
   before any balance reaches zero?
3. Can a transparent demand-aware hypergraph construction improve or preserve
   service reliability relative to NCH, FHS, and resource-matched binary PCNs
   on held-out and shifted demand?
4. How do locked capital, path length, signaling/coordination burden, and
   rebalancing interact with service reliability?
5. Are observed topology rankings stable across network size, parent-graph
   structure, traffic regime, initial imbalance, and Lightning structural
   cross-sections?

The project seeks conditional regimes and Pareto frontiers. It does not seek or
presuppose a topology that is universally optimal.

## 5. Planned contributions

### 5.1 Depletion-to-unavailability measurement framework

Use a common request clock to estimate:

- survival distributions of `tau_dep`, `tau_nopath`, and `tau_rej`;
- the probability of path unavailability within `h` requests after depletion;
- the censored lead-time distribution between events;
- the reverse event in which path unavailability precedes exact depletion;
- post-failure recovery time, consecutive-failure length, and cumulative
  success.

### 5.2 Resource-matched topology comparison

All primary topology comparisons match:

- node set and parent graph;
- per-node locked-capital budget;
- total incidence budget in the cost-matched panel;
- request source, destination, amount, and temporal trace;
- initial-balance rule and routing rule;
- optimization and simulation budget.

This contract isolates topology effects more credibly than comparisons that
allow capital, traffic, and construction resources to change simultaneously.

Because every binary channel contributes two incidences, exact per-run binary
matching is possible only for even source incidence budgets that also lie in
the connected simple-graph capacity range. These feasible even cells form the
strict cost-matched panel. Odd-budget cells report both adjacent binary
brackets with incidence deltas `-1` and `+1`; neither is mislabeled exact, and
no monotonic reliability assumption is made under fixed per-node capital.

### 5.3 Demand-aware HPN construction

Under a fixed incidence budget and maximum hyperedge arity, construct a
hypergraph using an explicit training objective with four terms:

1. reward high bidirectional demand captured inside hyperedges;
2. penalize directional demand imbalance;
3. penalize excessive per-node hyperedge participation;
4. penalize excessive hyperedge overlap or coordination burden.

The objective and every coefficient must be frozen in a training manifest.
Performance is evaluated only on independent in-distribution and
out-of-distribution request traces.

### 5.4 Topology-route-liquidity-service mechanism

For each topology and demand kernel, compute the demand-weighted route
incidence matrix and derive:

- per-balance load and negative drift;
- marginal variance and cross-hyperedge covariance;
- load concentration;
- alternative-path redundancy;
- path-length and hyperedge-arity exposure.

These descriptors are used to explain conditional performance heterogeneity,
not to claim causal effects in the public Lightning network.

## 6. System architecture

The implementation is a Python 3.10+ package with small, testable modules. A
flat package layout permits zero-install standard-library test replay in the
current research environment; the logical boundaries are:

```text
secondaryexploration/
  model/          # hypergraph, balances, requests, routes, atomic transitions
  topology/       # parent graphs, NCH, FHS, chain/star, binary baselines
  traffic/        # demand kernels, amounts, temporal traces, train/test splits
  routing/        # full feasible search, tie-breaking, robustness policies
  simulation/     # request-clock engine, event recorder, continuation logic
  metrics/        # survival, recovery, success, cost, route descriptors
  optimization/   # capacity allocation and demand-aware topology construction
  experiments/    # immutable manifests, paired runners, output validation
tests/
  unit/
  property/
  exact/
  integration/
configs/
  pilot/
  formal/
data/
  README.md       # provenance rules; raw external data are not committed blindly
results/
  README.md       # generated artifacts are linked to manifests and hashes
```

No module may read global experiment state implicitly. A simulation run is
fully determined by a validated configuration, an input-data manifest, and a
random-seed record.

## 7. State and atomic-payment semantics

For hypergraph `H=(V,E)`, each hyperedge `e` stores member balances `x[e,v]`
with fixed sum in the core model. A route is a sequence of hyperedge-local
transfers. An accepted payment updates every traversed hyperedge atomically;
partial updates are forbidden.

Core path feasibility for amount `a` requires every paying coordinate on the
route to have at least `a`. The core model has no fees, reserves, HTLC limits,
retry failure, or rebalancing. These mechanisms are introduced one at a time
in sensitivity experiments.

If a request fails, balances remain unchanged. Simulation continues after the
first failure until the common observation horizon so that recovery and
sustained service can be measured.

Required invariants include:

- per-hyperedge balance conservation in the core model;
- nonnegative balances;
- all-or-nothing route updates;
- no state change after a rejected request;
- event-clock monotonicity and exact first-event indexing;
- deterministic replay from manifest plus seeds.

## 8. Routing contract

### 8.1 Main service router

For every request, build the directed residual hypergraph and perform a full
global feasible search. Every hyperedge traversal costs one routing hop,
independent of arity. Among feasible paths:

1. minimize the number of traversed hyperedges;
2. among equal-length paths, maximize the minimum post-payment normalized
   directional balance;
3. resolve any remaining tie by reproducible uniform random choice.

For a route step paid by coordinate `(e,v)` with amount `a`, the normalized
post-payment directional balance is exactly
`(x[e,v] - a) / sum_u x[e,u]`. Implementations compare these values with exact
rational arithmetic; normalization by total hyperedge capital makes the
criterion comparable across heterogeneous channel sizes.

Search failure defines `tau_nopath`; a precomputed `K`-path candidate set is
not permitted in primary experiments.

### 8.2 Comparison routers

- Balance-independent uniform shortest-path routing provides the bridge to
  paper 1.
- Maximum-bottleneck routing is a robustness policy.
- Single-path atomic payment is primary; atomic multi-part payment is a
  sensitivity extension with split count and coordination cost reported.

## 9. Topology design

### 9.1 Deterministic theoretical anchors

- `k`-uniform overlap chains;
- `k`-uniform common-core stars/sunflowers;
- matched node count, hyperedge count, incidence count, and per-node capital;
- core arities `k in {2,3,5}` and overlap parameter `1 <= r < k`.

Small instances near nine nodes support exact enumeration and counterexamples.

For `m` hyperedges, the canonical chain uses sliding windows of length `k` and
stride `k-r`. Hyperedges `d` positions apart therefore intersect in
`max(0,k-d(k-r))` nodes; when `r>k/2`, nonconsecutive overlap is retained and
reported rather than silently excluded. The matched sunflower uses `r` common
core nodes and `k-r` disjoint private nodes per hyperedge. Both families have
`r+m(k-r)` nodes, `m` hyperedges, and `mk` incidences. The `k=2,r=1` cases are
the deterministic binary path/star anchors; this label does not assert
cross-arity resource matching, which is handled separately through shared
parent graphs.

### 9.2 Synthetic parent-graph ensembles

Use Erdős-Rényi, Barabási-Albert, and stochastic-block parent graphs. Within
each network size, match node count, total edge count, and mean degree so that
degree heterogeneity, clustering, and community structure remain the intended
differences. Disconnected draws are rejected according to a frozen resampling
rule.

The executable contract uses connected conditional fixed-edge `G(n,m)`, a
star-initialized BA process whose attachment count `a` yields exactly
`a(n-a)` edges, and a microcanonical SBM with declared exact within-block and
between-block edge counts. The BA edge count is the shared target within each
model-size-replicate block. Every draw records model-specific parameters, the
first accepted attempt, and a namespaced derived seed; public records replay
and validate their complete edge sets instead of trusting provenance labels.

Primary sizes are `n in {30, 60, 120, 240}`. Each model-size cell contains
multiple independent parent-graph instances.

### 9.3 Derived payment topologies

Each parent graph produces:

- a resource-matched binary PCN;
- a binary clique-expansion cost reference;
- NCH using the declared approximate vertex-cover implementation;
- FHS with core maximum arities 3 and 5;
- larger FHS arities as sensitivity conditions;
- the demand-aware HPN variant.

The matched binary selector first chooses a seed-priority Kruskal spanning tree
from parent edges, then adds remaining parent edges before any non-parent pair.
Lower and upper odd-budget brackets are nested and use stable pair identifiers.
This selector is reproducible and parent-preserving but is not claimed to draw
a uniform random spanning tree.

The primary NCH implementation uses a frozen canonical-order local-ratio
2-approximate vertex cover and creates closed-neighborhood hyperedges
`{c} union N(c)`. This is an explicit correction to the uploaded paper's
literal open-neighborhood pseudocode, which can create one-member channels and
orphan cover nodes. Primary FHS selects the canonical maximum-residual-degree
node, runs canonical BFS visiting at most `m_max` total nodes including the
seed, and removes all residual edges induced by that visited set. Both source
interpretations and every tie rule are recorded in formal manifests.

A single hyperedge containing all nodes is retained only as a theoretical
connectivity upper bound. It is never presented as an ordinary deployable
competitor.

### 9.4 Lightning structural panels

Treat the 2020, 2022, 2023, and 2026 datasets as separate structural
cross-sections, not a node-level longitudinal panel. At each size, sample
multiple connected subgraphs from core, bridge, and peripheral strata.

Two capital panels are reported:

1. equal per-node capital for fair topology comparison;
2. public-capacity-derived node-total heterogeneity for structural sensitivity,
   with initially equal directional splits explicitly labeled as an
   assumption.

The full largest connected component is a descriptive stress test only. Public
topology experiments cannot estimate real Lightning failure rates.

## 10. Traffic and amount design

Primary source-destination kernels are:

- uniform ordered pairs;
- community-local demand;
- exogenously labeled hotspot concentration;
- directional drift.

Hotspot labels are permuted across central, bridge, and peripheral roles rather
than selected as each topology's highest-degree node. All paired topologies use
the same request traces.

Main comparisons use i.i.d. requests. Markov-modulated hotspot movement and
bursty traffic retain matched long-run marginals and form temporal-dependence
sensitivities.

The executable iid contract represents every ordered source-destination pair
with a positive integer weight. Community blocks, hotspot labels, and the two
directional groups are exogenous canonical inputs shared by all paired
topologies. A hotspot pair receives one multiplier per hotspot endpoint;
directional drift assigns separate left-to-right, right-to-left, and
within-group weights. The complete integer table and its fingerprint are
authoritative, avoiding floating-point probability drift.

Request generation derives independent `traffic.pairs` and `traffic.amounts`
streams from one trace root. Changing an amount table therefore cannot change
the endpoint sequence, and changing a demand kernel cannot change the amount
sequence. The immutable generated request tuple is reused unchanged across all
topologies in a pairing block.

Amounts are normalized by per-node locked capital. Formal manifests use
prespecified small, medium, and large stress levels; a truncated heavy-tail
mixture is a secondary service workload. The uploaded HPN paper's amount
scaling is reproduced separately for comparability. Exact ratios are chosen in
the pilot by a declared coverage rule and frozen before formal inference; they
cannot be tuned to favor a topology.

Aggregate request intensity scales with node count. Cross-size outcomes are
reported as requests per node and cumulative attempted value divided by total
locked capital, not only as raw global request counts.

## 11. Capital, initial state, and optimization

Primary comparisons fix an equal capital budget per node. The baseline divides
each node's capital equally among its incident hyperedges. Hyperedge-internal
balances therefore begin at a declared balanced allocation.

Initial-state sensitivity uses total-capacity-preserving Dirichlet imbalance,
stratified by distance from the balanced state.

Capacity optimization is common to every topology:

1. initialize using training-demand load and balance-variance risk;
2. refine on each node's allocation simplex using the same projected stochastic
   optimization algorithm and evaluation budget;
3. optimize a robust lower quantile of `tau_nopath` across registered training
   regimes;
4. evaluate only on untouched test traces.

Uniform allocation remains a mandatory baseline. Topology-specific optimizers
are forbidden in the primary comparison.

## 12. Rebalancing and protocol sensitivities

The core experiment has no active rebalancing. A common fixed-threshold
rebalancing policy is added as a sensitivity condition, with rebalanced amount,
frequency, and cost reported separately.

Fees, reserve floors, and HTLC concurrency limits are introduced one mechanism
at a time before any combined scenario. This factorial layering prevents a
failure change from being attributed to the wrong mechanism.

Topology remains fixed within a primary run. Matched channel
deactivation-recovery is a robustness experiment; node joins, departures, and
hyperedge reconstruction are outside the first implementation scope.

## 13. Outcomes and statistical analysis

### 13.1 Primary outcome

The primary service outcome is a robust lower quantile of `tau_nopath` on the
normalized request clock. Because some runs will not fail within the
observation horizon, inference must retain right censoring.

### 13.2 Secondary outcomes

- survival curves and RMST;
- fixed-horizon failure risk;
- `tau_dep` warning performance;
- `tau_rej`, success rate, accepted value, and recovery metrics;
- path length and residual safety margin;
- locked capital, incidence count, coordination exposure, and rebalancing cost.

No arbitrary weighted total score is used. Reliability and cost are reported
as Pareto frontiers.

### 13.3 Paired and hierarchical design

The pairing block is:

> parent-graph instance + node mapping + request/amount trace.

All derived topologies run within the same block. Inference first computes
within-block contrasts and then resamples or models the independent parent-graph
level. Traffic trajectories within a parent graph are not treated as
independent topology replicates.

Simulation size is determined by an independent pilot, a prespecified smallest
effect of interest, and simultaneous-interval precision. Formal sample sizes
are frozen; simulation does not continue until significance appears. A fully
independent confirmation run uses a disjoint seed family.

### 13.4 Multiple comparisons

The confirmatory hierarchy is:

1. hypergraph-family versus resource-matched binary-family global contrast;
2. NCH, FHS, chain/star, and demand-aware contrasts only after the global test;
3. remaining cells labeled exploratory.

Effect sizes and simultaneous confidence intervals are reported regardless of
statistical significance.

## 14. Cost model

Primary cost reporting is dimensionless and component-wise:

- locked capital;
- incidence/construction count;
- number of participants signaled per route;
- number of traversed hyperedges;
- rebalanced value;
- multi-part split count when enabled.

Coordination cost uses a linear `|e|` baseline and `|e| log |e|` and `|e|^2`
sensitivity scenarios. Published dollar-weight scenarios may be reproduced for
comparison but cannot determine the main conclusion.

## 15. Demand-aware validation

The demand-aware topology is trained once per parent graph from training
traffic. It is evaluated on:

- an independent trace from the same demand distribution;
- hotspot relocation;
- direction reversal;
- increased cross-community demand.

An advantage observed only on the training distribution is reported as
overfitting, not as a reliability improvement.

## 16. Verification gates

Formal experiments cannot start until all applicable gates pass.

### Gate V1: Prior-paper semantic reproduction

Reproduce the direction of key NCH/FHS topology, shortest-available-path,
success-rate, and path-length findings using accessible versions of the
published inputs. Exact numerical identity is not required when versions
differ, but every discrepancy must have a documented cause or bounded
uncertainty.

### Gate V2: Process correctness

Pass unit and property tests for conservation, feasibility, atomicity,
rejection immutability, tie-breaking, clocks, recovery, and deterministic
replay.

### Gate V3: Independent small-network oracle

Cross-check the production engine against:

- exhaustive sequence enumeration;
- exact finite-state/Poisson calculations where feasible;
- a separately written small reference implementation.

### Gate V4: Independent result review

When a formal result family is complete, a subagent that did not implement the
feature independently audits the manifest, reruns a minimal reproduction,
checks estimands and intervals, and writes a review artifact. The implementer
does not self-certify the result.

### Gate V5: Formal freeze

Freeze configuration, input hashes, code commit, environment lock, seed
families, output schema, and analysis script before confirmatory runs.

## 17. Git and reproducibility policy

Use `codex/` branches. Commit and push at meaningful verified milestones:

1. approved research design;
2. tested project scaffold and schemas;
3. verified balance/state engine;
4. verified full feasible router;
5. reproduced prior-paper baseline;
6. frozen pilot and formal manifests;
7. each independently audited result family;
8. manuscript figures/tables and final reproduction bundle.

Each commit message names the achieved gate. A milestone is pushed only after
its relevant tests pass. Generated bulk outputs are stored according to a data
manifest and are not committed indiscriminately.

The review package available during submission must be anonymous. The public
release after de-anonymization includes version tags, environment files, input
hashes, and a permanent archive identifier.

## 18. Implementation sequence

The implementation will proceed in dependency order:

1. package scaffold, schemas, configuration validation, and deterministic RNG;
2. hypergraph state model and atomic request transition;
3. exact residual feasibility search and routing policies;
4. request-clock events, continuation, censoring, and recovery metrics;
5. deterministic chain/star and binary topology anchors;
6. ER/BA/SBM parent ensembles and NCH/FHS transformations;
7. traffic kernels and paired experiment runner;
8. survival/statistical analysis and cost components;
9. capacity optimizer and demand-aware topology constructor;
10. protocol, rebalancing, temporal, and multi-part sensitivities;
11. Lightning structural panels;
12. formal manifests, independent audits, and paper artifacts.

Each numbered item receives its own implementation plan or bounded plan slice;
the project will not attempt all subsystems in one unreviewable change.

## 19. Explicit non-goals and claim boundaries

The first implementation does not:

- estimate the real Lightning Network's failure rate or remaining lifetime;
- infer private directional balances or payment flows from public topology;
- claim that hypergraph PCNs universally outperform binary PCNs;
- claim that larger hyperedges are universally preferable;
- treat first depletion, path unavailability, and final rejection as synonyms;
- develop a joint `n,N -> infinity` high-dimensional theorem;
- model node arrival and hyperedge reconstruction;
- use a single volatile dollar-cost parameter to declare a permanent winner.

## 20. Risks and predetermined fallback rules

| Risk | Predetermined response |
|---|---|
| Demand-aware topology wins only in training | Report overfitting; retain it as a negative result or redesign only in a separately registered study. |
| Topology rankings change sign | Report conditional regimes; do not average away interactions. |
| Full exact search is too slow at `n=240` | Optimize the exact algorithm and profile; do not silently substitute a `K`-path approximation in primary experiments. |
| Large fraction of censored runs | Increase the registered horizon before formal freeze or emphasize RMST/fixed-horizon risk; never impute horizon as the event time. |
| Cost ranking depends on exponent/weights | Report the changed Pareto frontier and sensitivity boundary. |
| Lightning panels disagree across years | Treat the disagreement as structural heterogeneity, not a failed replication. |
| Prior-paper numerical reproduction differs | Diagnose versions and semantics; block new formal runs if the direction or mechanism cannot be reconciled. |

## 21. Design acceptance criteria

This specification is ready for implementation planning only if the reviewer
confirms that:

- the paper 1 / paper 2 boundary is correct;
- the event definitions match the intended operational meanings;
- the primary topology comparison and resource matching are acceptable;
- the demand-aware contribution is in scope;
- the primary outcome and statistical hierarchy are acceptable;
- the listed non-goals are acceptable;
- Python 3.11+ is an acceptable implementation platform.

After confirmation, the next required artifact is a detailed implementation
plan for sequence item 1. No production code is written before that plan.
