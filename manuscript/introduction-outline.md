# Introduction and Related Work outline

## Drafting argument

In hypergraph payment networks, we evaluate how topology, traffic and
balance-aware routing jointly shape service reliability using resource-matched
topologies, stateful paired execution and parent-stratified independent
confirmation, with conclusions limited to the registered synthetic and
structural-panel conditions.

## Primary reader and architecture

The primary reader is a networked-systems researcher familiar with payment
channels but not necessarily with hypergraph constructions. The Introduction
uses an **open-with-challenge** funnel: finite directional liquidity makes
route feasibility a stateful service problem, prior work addresses important
parts of that problem, and the present study connects the parts under a common
experimental contract.

## Introduction paragraph map

1. **Context — why PCNs matter.** Define payment-channel networks as an
   off-chain scaling mechanism and explain that multi-hop service depends on a
   path with sufficient directional liquidity. Cite R001 and a primary system
   source; avoid unqualified throughput numbers.
2. **Bottleneck — topology is not enough when balances evolve.** Explain that
   repeated directional traffic can deplete channels and that routing,
   rebalancing and topology/capacity design change how long service remains
   available. Cite R002--R010. Keep channel depletion distinct from first
   global path unavailability.
3. **Gap — the relevant strands remain only partially connected.** Synthesize
   demand-aware topology, depletion stopping time, HPN construction and
   multi-party path planning. Cite R005--R016. State that existing evidence
   does not by itself answer a resource-matched, stateful comparison across
   multiple parent-graph strata. Do not use “first”.
4. **Present study — contribution without results.** State the theory--experiment
   route separation, four topology families, three parent-model strata,
   train-once held-out evaluation, paired traces, primary service endpoints,
   parent-stratified bootstrap and independent confirmation. End with the
   synthetic and Lightning claim boundaries; do not preview effect direction.

## Related Work subsection map

Related Work remains a distinct section immediately after the Introduction.
This satisfies TNSM's explicit related-work-section requirement and keeps the
four-paragraph opening focused on the problem, gap and study design. Drafting
anchors `R001`--`R019` are replaced by IEEE numbered citations only when the
LaTeX bibliography is assembled.

### Routing, liquidity management and rebalancing

Group Spider, Flash, Revive and AERO by mechanism. The closing distinction is
that routing and rebalancing operate on a selected topology, whereas paper 2
compares topology families while holding the registered routing semantics and
resource panels fixed.

### Topology, capacity and service lifetime

Group Algorithmic Channel Design, demand-aware topology construction, the
IEEE/ACM topology models, Survivable PCNs, effective-lifespan modelling and the
DISC topology/transaction-selection work. The closing distinction is the event
definition: depletion-oriented lifetime measures cannot be silently substituted
for first globally unavailable path.

### Multi-party and hypergraph payment channels

Position the uploaded HPN paper as direct provenance, Corcoran--Lewis as
multi-party path planning, and the 2025--2026 preprints as emerging adjacent
protocol/theory work. The closing distinction is paper 2's resource-matched
stateful evaluation and phase-separated confirmation, not a claim to invent
multi-party channels or hypergraph routing.

### Empirical Lightning structure

Use empirical topology studies only to motivate structural heterogeneity and
the diagnostic cross-sections. Explicitly state that public gossip does not
identify private balances or payment flows and that the nested anchor samples
are not independent network replicates.

## Locked terminology

| Canonical term | Required distinction |
|---|---|
| hypergraph payment network (HPN) | Multi-party hyperedges; do not use as a synonym for every multi-party protocol. |
| first directional-balance depletion, `tau_dep` | A coordinate reaches zero; not necessarily service failure. |
| first path unavailability, `tau_nopath` | No globally feasible path for the current request under the declared protocol. |
| fixed-horizon failure risk | Whether `tau_nopath` occurs by the administrative horizon. |
| resource-matched binary reference | Binary arm(s) registered to the same source family, never a pooled generic baseline. |
| parent observation | Independent bootstrap unit after registered trace aggregation. |

## Claim--evidence map

| Planned claim | Evidence | Status |
|---|---|---|
| Finite directional liquidity makes PCN route feasibility stateful | R002--R004, R008--R010 | Supported |
| Topology and demand/capital allocation are coupled design choices | R005--R007, R013 | Supported |
| Depletion stopping time is established prior work but differs from `tau_nopath` | R008--R009 plus the frozen event definitions | Supported distinction |
| Multi-party PCNs can be modelled and routed as hypergraphs | R011--R012; R014--R016 as emerging context | Supported, with preprint labels |
| Existing work does not already contain the complete paper-2 design | Targeted search and source-by-source boundary audit | Provisionally supported; repeat before submission |
| Any HPN family improves service reliability | Formal and confirmation endpoint evidence | Not available; omit from Introduction |

## Remaining inputs before final prose

- Repeat the novelty search immediately before submission, including forward
  citation checks for the closest 2024--2026 papers.
- Add result-direction language only after complete formal and confirmation
  evidence passes strict replay and the registered hierarchy gates.
