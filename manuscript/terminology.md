# Terminology ledger

This ledger is the canonical terminology source for paper 2. Terms should not
be varied merely for style.

| Canonical term | First-use definition | Avoid or restrict |
|---|---|---|
| hypergraph payment network (HPN) | A finite hypergraph whose hyperedges are multi-party payment channels with conserved member balances | Do not use *hyperchannel network* as a synonym |
| binary payment-channel network (binary PCN) | A payment network in which every channel has exactly two participants | Use *binary comparator* only after the full term is defined |
| directional balance, `x_{e,v}` | The balance owned by participant `v` within hyperedge `e` | Do not call it edge capacity |
| request clock | The one-based index of every attempted request, accepted or rejected | Do not switch to transaction clock |
| first directional-balance depletion, `tau_dep` | The first request index after an accepted payment at which any directional balance becomes zero; `tau_dep=0` for an initially zero coordinate | Do not equate with network failure |
| first path unavailability, `tau_nopath` | The first request index for which no globally feasible path exists under the declared protocol | Do not abbreviate as depletion time |
| first final rejection, `tau_rej` | The first request index at which a request is rejected after the declared routing and retry policy | Distinct from `tau_nopath` outside the core protocol |
| balance-aware routing | Global feasible-path search on the current residual-balance state | Do not call it adaptive routing without qualification |
| parent graph | A connected simple graph from which matched payment topologies are derived | Distinct from a statistical parent observation |
| ER-GNM | Connected conditional fixed-edge Erdős–Rényi `G(n,m)` parent-graph stratum | Use this exact model label in tables |
| Barabási–Albert (BA) | The frozen star-initialized preferential-attachment parent-graph stratum | Define BA once |
| fixed-count stochastic block model (fixed-count SBM) | A microcanonical block-model parent graph with exact within- and between-block edge counts | Do not shorten to SBM where ambiguity matters |
| Node Cover Hypergraph (NCH) | Closed-neighborhood hyperedges generated from the frozen approximate vertex-cover rule | Retain the uploaded-paper semantic difference in limitations |
| Fixed Hyperedge Size 3 and 5 (FHS3 and FHS5) | Frozen bounded-BFS hypergraph constructions with maximum arity 3 or 5 | Do not write FHS-3/FHS-5 interchangeably |
| demand-aware HPN | A topology trained from training demand under fixed node, incidence and arity constraints | Do not imply global optimality |
| incidence budget | The sum of hyperedge arities, `sum_e |e|` | Distinct from hyperedge count |
| resource-matched binary reference | The exact mean of only the binary arm or arms registered to one source family | Do not pool binary arms across source families |
| pairing block | One parent-graph instance, node mapping and immutable request/amount trace evaluated across all registered variants | Traffic traces within a block are not independent topology replicates |
| parent observation | The `4:3` weighted combination of same-distribution and shifted trace contrasts within one parent graph | The independent bootstrap unit |
| model stratum | One of ER-GNM, BA or fixed-count SBM | Strata receive equal weight and are not pooled |
| normalized restricted no-path time | `tau_nopath.request_index / H`, with censored observations retained at the administrative horizon `H` | Larger values are beneficial |
| fixed-horizon failure risk | The indicator that `tau_nopath` was observed by `H` | Smaller values are beneficial |
| restricted mean survival time (RMST) | The discrete request-clock mean of survival through a prespecified horizon | Define once; use RMST thereafter |
| formal phase | The frozen primary experiment with root seed `2026081001` | Distinct from the independent confirmation phase |
| confirmation phase | The complete independent rerun with root seed `2026081002` | Never pool with the formal phase for confirmation |
| stratified parent-cluster bootstrap | Parent resampling within each model stratum followed by equal weighting of the three stratum means | Traffic traces are never bootstrap units |
