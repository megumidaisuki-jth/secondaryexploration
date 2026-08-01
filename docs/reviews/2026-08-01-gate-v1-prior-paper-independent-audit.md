# Gate V1 Prior-Paper Reproduction: Independent Audit

**Date:** 2026-08-01
**Final decision:** PASS
**Mode:** Independent read-only implementation and evidence audit

## Scope and first decision

The reviewer independently verified the uploaded-paper hash, public input
hashes, upstream commit, graph anchors, all nine structural rows, the comparison
router, and all four complete 10,000-request trajectories. The first review
kept the Gate blocked despite exact numerical agreement because:

1. the paper-anchor graph filter differed from the public dependency's
   two-policy and capacity-floor preprocessing but that difference was not yet
   in the discrepancy ledger; and
2. the compact replay result lacked input fingerprints and an explicit
   input-bound full-replay validator.

After those were fixed, a second review found a structural serialization
collision: field lengths were framed, but node, edge, and member-list
boundaries were not. Two different topology/state pairs therefore produced an
identical manifest, result, and final-balance hash without a SHA-256 collision.

## Remediation verified

The final v2 fingerprints use separate domains and explicitly encode node
count, edge count, per-edge member or balance-entry count, and request count.
The validator first binds topology, initial state, request trace, amount
multiplier, and routing seed to the manifest, then fully re-executes the
comparison policy and requires exact result identity.

The original collision vector is now a regression test. The reviewer also
tested 186 additional member/edge boundary re-partition attacks plus request
order and amount changes; all were rejected. Forged outcomes and final hashes
were rejected by full replay.

The discrepancy ledger now states that:

- the Gate anchor rule gives 61,966 simple edges and 11,268 nodes;
- requiring both directional policies gives 61,542 edges and 11,135 nodes;
- adding the public dependency's 60,000 SAT capacity floor gives 59,849 edges
  and 10,511 nodes; and
- Gate V1 is a declared anchor-matching semantic reproduction, not an unchanged
  rerun of the dependency or the unavailable HPN simulator.

It also records the doubled exact-unit scale, 120,000-unit executed request,
the post-observation descriptive 0.05-hop tolerance, and that 10.99858 rounds
conventionally to 11.00 rather than the paper's displayed 10.99.

## Independent numerical evidence

The reviewer reconstructed the public input as 11,268 nodes, 61,966 simple
edges, 123,932 binary incidences, mean degree 10.99858004969826, construction
cost 743,592, and 349 out-of-graph requests. Independent NCH/FHS construction
matched every tracked structural row.

All four full trajectories were independently rerun after v2 fingerprinting.
Counts, hop sums, topology hashes, initial-state hashes, common request-trace
hash, and final-balance hashes matched the tracked summary exactly:

| Topology | Accepted | No path | Outside | Hop sum | Final balance SHA-256 |
|---|---:|---:|---:|---:|---|
| LN | 7,993 | 1,658 | 349 | 21,159 | `6c809470...cbffd27` |
| NCH published order | 8,269 | 1,382 | 349 | 12,961 | `b9485bd8...17b4987` |
| FHS-5 | 8,286 | 1,365 | 349 | 20,302 | `5e11b13a...4ce269f` |
| FHS-50 | 8,314 | 1,337 | 349 | 16,719 | `85a1e600...bf2cc4c` |

Before v2, the reviewer also compared the accelerated engine with an
independently written exhaustive residual-BFS route enumerator on 301 small
graph cases covering 6,001 requests, and compared the isolated comparison
router on 500 random queries and 535 route tickets. Every outcome, chosen path,
and final balance agreed, including the longer-residual-path fallback case.

## Focused verification

The final focused Gate suite passed 19/19 tests on both Python 3.10.16 and
Python 3.12.13. The independent reviewer made no repository modifications.
