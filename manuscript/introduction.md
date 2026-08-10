# Introduction and Related Work (working draft)

> **Drafting argument.** In hypergraph payment networks, we evaluate how
> topology, traffic and balance-aware routing jointly shape service reliability
> using resource-matched topologies, stateful paired execution and
> parent-stratified independent confirmation. Conclusions are limited to the
> registered synthetic and structural-panel conditions.
>
> Citation anchors `R001`--`R019` refer to
> [the verified positioning ledger](citations/intro-related-work-claims.md).
> They are drafting identifiers, not the final IEEE reference numbers. This
> result-free draft must not acquire effect-direction language until both
> registered phases pass strict replay and inference.

## I. Introduction

Payment-channel networks (PCNs) move repeated transfers away from a base-layer
ledger while retaining the ledger as the settlement and dispute-resolution
backstop [R001]. A multi-hop payment, however, is serviceable only when the
network can assemble a route whose channels provide sufficient liquidity in
the required direction. The transfer then changes those directional balances,
so the feasible route set for the next request depends on the complete history
of earlier requests and routing decisions. In multi-party channels, one
contractual relation can join more than two participants and is therefore
naturally represented by a hyperedge rather than an ordinary graph edge
[R011, R012]. This higher-order structure expands the topology-design space,
but it does not remove the finite-liquidity constraint that makes availability
stateful.

This state dependence separates snapshot connectivity from sustained service.
Repeated directional demand can exhaust one side of a channel even though its
endpoints remain connected in the static graph [R002]. Dynamic routing can
distribute load using balance or congestion information [R002, R003, R010],
and rebalancing can redistribute liquidity without closing every affected
channel [R004]. Topology and capacity design can instead change which routes
exist and where capital is placed [R005, R006, R007, R013]. These mechanisms act at
different layers, and their service events are not interchangeable. In
particular, the first directional balance to reach zero may occur while other
feasible routes remain, whereas first path unavailability records the first
request for which no route is feasible under the declared routing and atomic
execution protocol. A topology may therefore appear fragile under a
coordinate-depletion clock yet continue to serve requests, or retain positive
balances while failing a particular request because no end-to-end feasible
path remains.

Prior research supplies the necessary pieces but does not, by itself, settle
their joint comparison. Demand-aware and model-based PCN designs formalize the
coupling among topology, capital and expected traffic [R005, R006, R007, R013], while
survivability and effective-lifespan studies make depletion time an explicit
design object [R008, R009]. Hypergraph payment-network constructions introduce
multi-party topology families [R011], and separate work establishes path
planning for multi-party channels [R012]. Recent preprints further develop
multi-party feasibility, protocols and rebalancing [R014, R015, R016]. The remaining
question is narrower than claiming that topology, depletion or hypergraph
routing has not been studied: under common capital, traffic, routing and
evaluation rules, how do alternative hypergraph topology families affect
service reliability as balances evolve, and does any observed direction
persist across heterogeneous parent-graph strata and an independent phase?

We address this question with a theory--experiment separation. The theory
layer defines the balance process and stopping-time relationships without
committing to an empirical route-selection heuristic. The experiment layer
then instantiates an exact balance-aware route protocol and compares
neighbourhood-based, fixed-hyperedge-size and demand-aware HPN constructions,
together with resource-matched binary references. Synthetic panels use
connected ER-GNM, Barabási--Albert and fixed-count stochastic-block parent
graphs; topology training is separated from held-out traffic, request objects
are paired within each parent, and inference aggregates nested traces before
resampling independent parents within model strata. The two registered primary
endpoints are normalized restricted time to first path unavailability and
fixed-horizon failure risk. A disjoint-seed confirmation phase repeats the
complete design without pooling phases. Lightning Network cross-sections are
used only as bounded structural diagnostics: public topology does not identify
private balances or payment flows, and overlapping anchor samples are not
treated as independent network replicates. This design supports a controlled
test of service reliability while keeping the claim boundary explicit before
any result is read.

## II. Related Work

### A. Routing, liquidity management and rebalancing

Routing research addresses the immediate allocation of finite directional
liquidity. Spider divides payments and uses congestion feedback to balance
traffic across binary-channel paths, directly illustrating how persistent
one-way demand can drain a route [R002]. Flash uses dynamic balance information
and payment-size classes to choose among paths [R003], whereas AERO incorporates
post-transaction imbalance when targeting longer-run throughput [R010]. Revive
instead coordinates off-chain redistribution of channel balances [R004]. These
approaches establish that route choice and liquidity management affect future
feasibility, but they operate on an already selected network. Our comparison
holds the registered routing semantics, traffic panels and capital rules fixed
while varying topology families. Rebalancing is outside the current
experimental protocol and is not assumed to erase every no-path event.

### B. Topology, capacity and service lifetime

Algorithmic channel design frames the network itself as an optimization object
under transaction demand and capital constraints [R005]. Demand-aware channel
topologies and subsequent model-and-construction work extend this view through
user placement, bounded channel resources and traffic-sensitive mappings
[R006, R007]. Joint topology optimization and transaction selection further
connects construction, augmentation and rejection cost [R013]. Closest to our
service-lifetime framing, Survivable Payment Channel Networks defines channel
and network depletion stopping times and studies capacity allocation against a
minimum stopping-time criterion [R008]; effective-lifespan modelling likewise
connects binary-channel imbalance time to network structure [R009]. These works
motivate a temporal reliability endpoint, but their depletion events cannot be
substituted silently for first path unavailability. We therefore retain both
coordinate-depletion records and request-level no-path records, while reserving
formal inference for the prespecified service endpoints.

### C. Multi-party and hypergraph payment channels

The HPN construction study is the direct topology provenance for this project:
it represents multi-party channels as hyperedges and introduces the
neighbourhood and fixed-hyperedge-size construction families [R011]. Corcoran
and Lewis treat multi-party path planning as a distinct algorithmic problem and
provide a graph reduction for finding routes through multi-party channels
[R012]. Emerging preprints broaden the adjacent landscape through a geometric
feasible-wealth theory that discusses multi-party channels and depletion
[R014], a leaderless hypergraph-based payment-channel protocol [R015], and a
multi-party rebalancing construction [R016]. We treat these sources according
to their evidential status and do not claim to invent multi-party channels,
hypergraph routing or rebalancing. The present distinction is the
resource-matched, stateful comparison of topology families with held-out
traffic and phase-separated confirmation.

### D. Empirical Lightning structure

Empirical studies of the Lightning Network document changing topology,
heterogeneous node and channel characteristics, and centrality structure
[R017, R018, R019]. These observations motivate checking whether conclusions drawn
from canonical random-parent ensembles remain structurally plausible across
different public graph regions and years. They do not provide private channel
balances, realized payment demand or causal interventions. Accordingly, our
Lightning panels preserve source identity, year and anchor stratum, disclose
nested-size and cross-anchor overlap, and remain outside the synthetic
parent-stratified confirmatory bootstrap. A core-, bridge- or
peripheral-anchored sample describes the anchor's global stratum; it does not
assert that the induced subgraph as a whole inherits that label or constitutes
an independent network replicate.

## Assumptions or missing inputs

- No performance direction is stated because formal and confirmation evidence
  is incomplete.
- The targeted positioning search is sufficient for drafting but must be
  repeated with the final title and abstract immediately before submission.
- Final IEEE reference numbers will replace `R001`--`R019` after the TNSM
  LaTeX package is downloaded through the frozen selector route.
