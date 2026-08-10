# Introduction and Related Work citation claims

**Search date:** 2026-08-09

This ledger records the claim that each source may support and, equally
importantly, the claim it may not support. Discovery used OpenAlex and web
search; bibliographic fields were checked against Crossref, publisher or
proceedings metadata, and support was checked against an abstract or accessible
paper page. Preprints are labelled explicitly and must not carry a stronger
novelty or performance claim than their evidence permits.

## Search scope

The query families covered: payment-channel routing under finite directional
liquidity; rebalancing and channel depletion; topology, capacity and
demand-aware channel design; stopping time and effective lifespan; multi-party
and hypergraph payment channels; and empirical Lightning topology. This is a
targeted positioning search, not yet the final submission-date systematic
novelty search.

## Core positioning sources

| ID | Source | Allowed support | Boundary and use in paper 2 | Grade |
|---|---|---|---|---|
| R001 | Papadis and Tassiulas, 2020, *Blockchain-Based Payment Channel Networks: Challenges and Recent Advances*, IEEE Access, [doi:10.1109/ACCESS.2020.3046020](https://doi.org/10.1109/ACCESS.2020.3046020) | PCNs move repeated transactions off chain but create routing, liquidity and privacy challenges. | Review/context only; prefer primary papers for specific algorithms or effects. | Background support |
| R002 | Sivaraman et al., 2020, *High Throughput Cryptocurrency Routing in Payment Channel Networks*, NSDI, [USENIX paper page](https://www.usenix.org/conference/nsdi20/presentation/sivaraman) | One-direction traffic can deplete binary channels; multipath congestion control can promote balanced use. | Spider packetizes payments and optimizes throughput in binary PCNs. It does not establish paper 2's atomic hypergraph semantics or service endpoints. | Strong support |
| R003 | Wang et al., 2019, *Flash: Efficient Dynamic Routing for Offchain Networks*, CoNEXT, [doi:10.1145/3359989.3365411](https://doi.org/10.1145/3359989.3365411) | Dynamic balance information and payment-size heterogeneity matter for routing; Flash separates elephant and mice payments. | Supports the routing-design context, not a long-horizon topology-survival claim. | Strong support |
| R004 | Khalil and Gervais, 2017, *Revive: Rebalancing Off-Blockchain Payment Networks*, CCS, [doi:10.1145/3133956.3134033](https://doi.org/10.1145/3133956.3134033) | Channel depletion motivates off-chain balance redistribution. | Revive is a rebalancing protocol, not a topology-construction method and not evidence that rebalancing removes every no-path event. | Strong support |
| R005 | Avarikioti, Wang and Wattenhofer, 2018, *Algorithmic Channel Design*, ISAAC, [doi:10.4230/LIPIcs.ISAAC.2018.16](https://doi.org/10.4230/LIPIcs.ISAAC.2018.16) | Payment-network design couples topology, capital allocation and transaction acceptance. | Graph-channel design and algorithmic bounds; it does not evaluate multi-party hyperedges under paper 2's stateful execution contract. | Strong support |
| R006 | Khamis and Rottenstreich, 2021, *Demand-aware Channel Topologies for Off-chain Payments*, COMSNETS, [doi:10.1109/COMSNETS51098.2021.9352899](https://doi.org/10.1109/COMSNETS51098.2021.9352899) | User placement and bounded-channel topology can be optimized toward associated payments. | Supports demand-aware topology motivation. Do not cite it as evidence for paper 2's residual-balance dynamics or stopping-time endpoints. | Strong support |
| R007 | Khamis, Kotzer and Rottenstreich, 2024, *Topologies for Blockchain Payment Channel Networks: Models and Constructions*, IEEE/ACM Transactions on Networking, [doi:10.1109/TNET.2024.3445274](https://doi.org/10.1109/TNET.2024.3445274) | Off-chain topology and payment characteristics affect routing distance, fees and required capacities; topology mapping and construction are algorithmic design problems. | Closely related topology work, but not a parent-stratified comparison of hypergraph service reliability under evolving balances. | Strong support |
| R008 | Podiatchev, Orda and Rottenstreich, 2024, *Survivable Payment Channel Networks*, IEEE TNSM, [doi:10.1109/TNSM.2024.3456229](https://doi.org/10.1109/TNSM.2024.3456229) | Defines depletion stopping time for channels and networks and studies capacity allocation to increase a minimum stopping-time criterion. | The closest service-lifetime antecedent. Its depletion stopping time must not be equated with paper 2's first globally unavailable path, `tau_nopath`. | Strong support |
| R009 | Shabgahi et al., 2022/2023, *Modeling Effective Lifespan of Payment Channels*, IACR ePrint 2022/1376 / arXiv:2301.01240, [arXiv](https://arxiv.org/abs/2301.01240) | Models a binary channel's expected time to imbalance and relates lifespan to topology. | Preprint evidence; channel-level imbalance is not the same event as network-level path unavailability. | Partial support; preprint |
| R010 | Huang et al., 2025, *AERO: An Adaptive and Efficient Routing for Off-Chain Payment Channel Networks*, Computer Networks, [doi:10.1016/j.comnet.2024.111009](https://doi.org/10.1016/j.comnet.2024.111009) | Routing that accounts for post-transaction imbalance can target longer-term throughput rather than only instantaneous success. | Routing-only comparison on binary PCNs; not a resource-matched hypergraph topology experiment or independent confirmation design. | Strong support |
| R011 | Kotzer et al., 2025, *Addressing Scalability Issues of Blockchains With Hypergraph Payment Networks*, IEEE TNSM, [doi:10.1109/TNSM.2025.3542960](https://doi.org/10.1109/TNSM.2025.3542960) | Introduces HPNs and the NCH/FHS construction family and compares success and cost outcomes. | Direct provenance for paper 2. It does not establish paper 2's corrected NCH semantics, service endpoints, parent strata or confirmation claims. | Strong support |
| R012 | Corcoran and Lewis, 2025, *Path Planning in Payment Channel Networks with Multi-Party Channels*, DLT Research and Practice, [doi:10.1145/3702248](https://doi.org/10.1145/3702248) | Models multi-party PCNs as hypergraphs and gives a correct path-planning reduction. | Establishes that multi-party path planning is a separate problem. It assumes suitable contract mechanisms and does not compare stateful service reliability across topology families. | Strong support |
| R013 | Chatterjee et al., 2025, *Boosting Payment Channel Network Liquidity with Topology Optimization and Transaction Selection*, DISC, [doi:10.4230/LIPIcs.DISC.2025.23](https://doi.org/10.4230/LIPIcs.DISC.2025.23) | Jointly designs topology/capacity and transaction acceptance to control construction, augmentation and rejection cost. | Recent close topology-and-lifetime work in binary PCNs. Its objective and approximation setting differ from paper 2's paired HPN service endpoints. | Strong support |

## Emerging adjacent work

| ID | Source | Allowed support | Boundary and use in paper 2 | Grade |
|---|---|---|---|---|
| R014 | Pickhardt, 2026, *A Mathematical Theory of Payment Channel Networks*, arXiv:2601.04835, [arXiv](https://arxiv.org/abs/2601.04835) | A geometric feasible-wealth model connects cuts, liquidity and multi-party channels and discusses depletion. | Recent unreviewed preprint. It narrows any claim that multi-party feasibility and depletion have not been studied, but it does not replace experimental evidence. | Partial support; preprint |
| R015 | Nainwal, Kamble and Awathare, 2025, *Hypergraph based Multi-Party Payment Channel*, arXiv:2512.11775, [arXiv](https://arxiv.org/abs/2512.11775) | Proposes a leaderless hypergraph-based multi-party channel protocol and reports an implementation study. | Recent unreviewed preprint with a different protocol and evaluation. It must be discussed as adjacent implementation work, not used to validate paper 2's simulator. | Partial support; preprint |
| R016 | Xu et al., 2025, *Starfish: Rebalancing Multi-Party Off-Chain Payment Channels*, arXiv:2504.20536, [arXiv](https://arxiv.org/abs/2504.20536) | Extends rebalancing to a multi-party, star-shaped construction. | Recent unreviewed protocol work; it addresses rebalancing rather than topology-family service comparison. | Partial support; preprint |

## Lightning structural context

| ID | Source | Allowed support | Boundary and use in paper 2 | Grade |
|---|---|---|---|---|
| R017 | Martinazzi and Flori, 2020, *The Evolving Topology of the Lightning Network*, PLOS ONE, [doi:10.1371/journal.pone.0225966](https://doi.org/10.1371/journal.pone.0225966) | Public Lightning snapshots exhibit time-varying structural properties relevant to centralization and robustness. | Public graph structure does not reveal private balances, payment flows or causal year effects. | Strong structural support |
| R018 | Zabka et al., 2022, *Empirical Evaluation of Nodes and Channels of the Lightning Network*, Pervasive and Mobile Computing, [doi:10.1016/j.pmcj.2022.101584](https://doi.org/10.1016/j.pmcj.2022.101584) | Empirical node/channel characteristics motivate treating Lightning graphs as structural data rather than generic random graphs. | Does not supply the private dynamic state required to estimate real payment-failure rates. | Strong structural support |
| R019 | Zabka et al., 2024, *A Centrality Analysis of the Lightning Network*, Telecommunications Policy, [doi:10.1016/j.telpol.2023.102696](https://doi.org/10.1016/j.telpol.2023.102696) | Centrality is a relevant structural lens for Lightning topology. | It does not validate paper 2's core/bridge/peripheral anchors as independent network replicates. | Strong structural support |

## Safe contribution statement

The current evidence supports the following bounded positioning:

> Prior work has studied binary-PCN routing and rebalancing, demand-aware
> topology and capacity design, depletion-based stopping times, hypergraph
> topology construction, and multi-party path planning. Paper 2 combines these
> strands in a resource-matched, stateful HPN study whose primary service event
> is first global path unavailability rather than first coordinate depletion,
> and whose claims require independent confirmation across parent-graph strata.

Do not turn this into a “first” claim. Before submission, repeat the search with
the final title/abstract and check citing and cited-by records for R008, R010--R016.
