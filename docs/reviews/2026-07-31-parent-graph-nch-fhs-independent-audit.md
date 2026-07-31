# Independent Audit: Parent Graph, NCH, and FHS Transformations

**Date:** 2026-07-31

**Reviewer:** Independent `metric_semantics` subagent; read-only review with no
repository modifications.

**Scope:** Canonical simple parent graphs, the frozen local-ratio vertex cover,
direct binary and clique references, closed-neighborhood NCH, residual-graph
FHS, and end-to-end compatibility with capital allocation and service routing.
Random graph generation, incidence-matched binary selection, and performance
claims were outside scope.

## Source-interpretation audit

The reviewer checked the declaration against Algorithms 2-3 of the uploaded
HPN paper.

- Algorithm 2 literally names the open neighborhood `N(c)`. The project does
  not claim a literal reproduction: it explicitly registers the deviation and
  uses `{c} union N(c)` to avoid one-member channels and orphaned cover nodes.
  The two-node counterexample, complete parent-edge co-containment, full node
  participation, and output connectivity are internally consistent.
- Algorithm 3 states that BFS visits `m_max` nodes in total, while the prose can
  be read as the seed plus `m_max` neighbors. Following the algorithm and the
  FHS-3/FHS-5 labels, the implementation counts the seed inside the maximum
  arity. This ambiguity is disclosed rather than hidden.

The linked paper artifact does not contain transformation source code, so
unspecified iteration order cannot be recovered. Canonical identifier ordering
is therefore a declared project rule.

## Independent checks

The reviewer confirmed:

- graph endpoints, nodes, edges, neighbors, degrees, and connectivity are
  canonical and fail closed under fourteen adversarial constructor or
  transformation inputs;
- the unweighted local-ratio implementation matches official NetworkX 3.4.2
  output on all **1,099** labeled graphs through five nodes, including the
  `<=` endpoint tie, residual-cost update, and covered-edge skip;
- exact minimum-cover enumeration verifies the 2-approximation bound on every
  one of those graphs;
- an independently written residual-edge reference reproduces maximum-degree
  selection, identifier ties, bounded BFS including the seed, induced-edge
  removal, residual-isolate handling, and output order for all **771** connected
  parent graphs and **3,035** FHS maximum-arity cells;
- NCH and FHS co-contain every parent edge, preserve every node, remain
  connected, and obey their declared arity rules;
- FHS with maximum arity two recovers exactly the parent binary edge multiset;
  and
- clique expansion preserves repeated participant pairs from different source
  hyperedges, with binary edge count equal to source pairwise exposure and
  binary incidence equal to twice that count.

The new focused suite passed **18/18 tests**: 14 unit, two exact, one exhaustive
property, and one integration test. The complete repository suite passed
**132/132 tests** under both Python 3.10.16 and the bundled Python 3.12.13; the
second interpreter check was run by the primary agent because it was not on the
reviewer's default command path.

## Final verdict

**PASS - eligible for the `verified parent graph and NCH/FHS transformations`
milestone.** No blocking defect was found within the reviewed scope.

## Claim boundary

This audit verifies declared structure and determinism, not equivalence to an
unpublished author implementation or reproduction of the paper's numerical
tables. The NCH closed-neighborhood deviation and FHS size interpretation must
remain visible in every formal manifest and manuscript methods section.
