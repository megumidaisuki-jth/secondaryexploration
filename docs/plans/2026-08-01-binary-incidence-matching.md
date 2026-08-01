# Binary Incidence-Budget Matching Contract

**Date:** 2026-08-01

**Milestone:** Deterministic parent-preserving binary baselines at exact or
adjacent incidence budgets.

## Mathematical boundary

Every binary channel contributes exactly two node-channel incidences. Within
the feasible channel-count range of a connected simple graph, a binary PCN can
therefore match source incidence budget `I` exactly if and only if `I` is even.
No implementation may label an odd-budget comparison as an exact per-run
match.

- Even `I`: one exact binary topology with `I/2` channels.
- Odd `I`: a nested lower/upper bracket with `floor(I/2)` and `ceil(I/2)`
  channels, hence incidence deltas `-1` and `+1`.
- Odd cells are adjacent-budget sensitivity cells, not strict cost-matched
  confirmatory cells. Both brackets are reported; no monotonic reliability
  assumption is made because adding a channel also redistributes fixed node
  capital.

A connected simple binary graph on `n` nodes requires between `n-1` and
`choose(n,2)` channels. Targets outside this lattice fail explicitly. Parallel
binary channels are not introduced silently.

## Parent-preserving selector

The selector receives a connected canonical parent graph, a source incidence
budget, and an unsigned 64-bit root seed.

1. Give every unordered node pair a stable SHA-256 priority framed by the root
   seed and both UTF-8 identifiers.
2. On parent edges, run priority-ordered Kruskal to choose a spanning tree.
3. If the target is no larger than the parent edge count, add remaining parent
   edges in priority order.
4. If the target is larger, retain every parent edge and add non-parent pairs
   in priority order.
5. Assign each participant pair an identifier derived only from its canonical
   node indices, so a shared pair has the same channel identifier in the lower
   and upper bracket.

Consequences:

- every feasible result is simple, connected, and uses the full node set;
- lower edges are a subset of upper edges;
- targets below the parent edge count are connected parent subgraphs;
- a target equal to the parent edge count reproduces the parent memberships;
- targets above it preserve all parent edges before adding new pairs; and
- selection is independent of source-family labels and payment traffic.

The priority spanning tree is reproducible but is not claimed to be a uniform
random spanning tree.

## Provenance and fail-closed records

The immutable match record stores the parent graph, source incidence budget,
root seed, and both output topologies. Direct construction re-runs the selector
and rejects altered budgets, roots, nodes, edge sets, connectivity, or bracket
ordering.

`match_binary_to_topology` additionally requires exact equality between the
source topology and parent node sets. Only the source incidence count affects
selection; hypergraph-family structure is not leaked into the binary selector.

## Verification gates

1. Known pair-priority and topology vectors freeze the selector.
2. Invalid parity/capacity, disconnected parents, node mismatch, bad seeds,
   and forged records fail closed.
3. Exhaust all 771 connected labeled parent graphs through five nodes and
   every feasible incidence target: 9,743 match cells.
4. Verify exact counts, connectivity, simplicity, nesting, parent preference,
   stable identifiers, and replay in every cell.
5. Verify all 36 primary ER/BA/SBM x NCH/FHS3/FHS5 cells; the current frozen
   pilot contains 16 exact even-budget and 20 odd-budget bracket cells.
6. Run the complete suite on Python 3.10 and 3.12 and obtain a read-only
   independent audit before commit.
