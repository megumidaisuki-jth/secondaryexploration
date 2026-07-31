# Canonical Parent Graph, NCH, and FHS Transformation Contract

**Date:** 2026-07-31

**Milestone:** Verified deterministic parent-graph representation, binary and
clique references, Node Cover Hypergraph (NCH), and Fixed Hyperedge Size (FHS)
transformations (first half of research design implementation sequence item 6).

## Evidence and scope

The source interpretation was checked against Section IV-A and Algorithms 2-3
on pages 7-8 of Kotzer et al., *Addressing Scalability Issues of Blockchains
With Hypergraph Payment Networks*. The paper's linked [artifact
repository](https://github.com/iAradK/improving-Blockchain-Scalability-with-Hypergraph-Payment-Networks)
contains traffic/topology data but no NCH/FHS transformation implementation,
so unspecified ordering cannot be recovered from code.

The paper states that NCH uses NetworkX
`min_weighted_vertex_cover`. The official [NetworkX source and
contract](https://networkx.org/documentation/stable/_modules/networkx/algorithms/approximation/vertex_cover.html)
identify this as a local-ratio 2-approximation. This project freezes an
unweighted, canonical-edge-order implementation so results do not drift with a
third-party version or insertion order.

This slice does not yet generate ER/BA/SBM graphs or construct an
incidence-budget-matched binary subset. Those follow after the transformations
are independently verified.

## Canonical parent graph

- A parent graph is finite, simple, undirected, and balance-free.
- Nodes and undirected edges are immutable canonical tuples. An edge stores
  endpoints in ascending identifier order; self-loops, duplicate edges, and
  unknown endpoints are rejected.
- Neighbor order, edge order, degree ties, and BFS ties all use canonical node
  identifiers. Identifier assignment is therefore part of every experiment
  manifest.
- The structure can represent disconnected graphs for diagnostic purposes,
  but primary NCH/FHS inputs must contain at least two nodes, at least one edge,
  no isolates, and one connected component.

## Binary references

- The direct binary topology converts every parent edge into one distinct
  two-member hyperedge and preserves the complete parent node set.
- The clique expansion of a hypergraph creates one two-member channel for every
  unordered pair inside every source hyperedge. Repeated participant pairs from
  different source hyperedges remain distinct channels.
- Consequently, clique-expansion hyperedge count equals the source topology's
  pairwise member exposure and its incidence count is twice that value.

Clique expansion is a construction-cost reference, not the cost-matched binary
primary competitor.

## Canonical local-ratio vertex cover

Initialize every node cost to one and scan parent edges in canonical order. For
an uncovered edge `(u,v)`:

1. if `cost[u] <= cost[v]`, add `u` and subtract `cost[u]` from `cost[v]`;
2. otherwise add `v` and subtract `cost[v]` from `cost[u]`.

The output must cover every parent edge and have cardinality at most twice the
exact minimum cover on exhaustively enumerable graphs. This is the declared
paper-compatible approximation; it is not claimed to be an exact minimum.

## NCH interpretation and deviation register

For every cover node `c`, primary NCH creates the closed-neighborhood hyperedge
`{c} union N(c)`.

The literal line 4 of paper Algorithm 2 names only the open neighborhood
`N(c)`. On a two-node graph this produces a one-member "channel" and omits the
cover node from every hyperedge, contradicting the payment-channel model and
the surrounding goal of preserving adjacent endpoint relationships. Because
the linked artifact contains no transformation code, the ambiguity cannot be
resolved empirically. The primary experiment therefore freezes the
closed-neighborhood interpretation and labels it explicitly; a literal-open
reproduction is not silently substituted.

Distinct cover nodes create distinct hyperedges even if their closed
neighborhood memberships coincide. For a connected input, every parent edge
must be co-contained in at least one NCH hyperedge, every node must participate,
and the output incidence hypergraph must be connected.

## FHS interpretation

Given maximum arity `m_max >= 2`, maintain a residual copy of the parent graph.
While residual edges remain:

1. choose the positive-degree node of maximum residual degree, breaking ties by
   canonical identifier;
2. run canonical BFS from that node and stop after visiting at most `m_max`
   total nodes, including the seed;
3. create one hyperedge from the visited nodes;
4. remove every residual edge whose two endpoints are both visited; and
5. ignore newly isolated nodes in later iterations while preserving them in the
   output node set.

The paper prose says "the node ... and its `m_max` closest neighbors", whereas
Algorithm 3 says BFS visits `m_max` nodes and the reported FHS-3/FHS-5 labels
refer to total hyperedge size. This project follows the algorithm and labels:
`m_max` is total maximum arity, including the seed.

Every iteration removes at least one edge. Every output hyperedge is connected
in the residual graph at creation, has arity in `[2,m_max]`, and every original
parent edge is co-contained in at least one output hyperedge.

## Test-first sequence

1. Lock canonical graph construction, simple-edge invariants, degrees,
   neighbors, connectivity, and exact mean degree.
2. Lock known local-ratio outputs and exhaustively compare the 2-approximation
   guarantee with exact minimum covers for all small labeled graphs.
3. Lock the two-node NCH counterexample motivating closed neighborhoods, plus
   parent-edge coverage, participation, and connectivity.
4. Lock deterministic FHS traces on paths, cycles, and dense graphs; verify
   maximum arity, residual edge removal, and complete parent-edge coverage.
5. Lock direct binary conversion and multiplicity-preserving clique expansion.
6. Integrate transformed topologies with equal-node-capital initialization only
   on budgets divisible by every incidence degree.
7. Run both supported Python versions and obtain an independent read-only audit
   before committing.

## Claim boundary

Passing this milestone establishes deterministic structural transformations
under the declared interpretations. It neither reproduces the paper's numerical
results nor establishes that NCH/FHS improves service reliability. The NCH
closed-neighborhood deviation and every tie rule must remain visible in the
manuscript and formal manifests.
