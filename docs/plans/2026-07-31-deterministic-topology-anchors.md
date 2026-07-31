# Deterministic Topology Anchors and Resource Accounting

**Date:** 2026-07-31

**Milestone:** Verified deterministic `k`-uniform overlap-chain,
common-core sunflower, and binary-anchor constructors (research design
implementation sequence item 5).

## Scope

This slice introduces an immutable balance-free topology representation,
deterministic theoretical anchor families, exact structural resource counts,
and the baseline equal-per-node-capital initializer needed by the verified
state engine.

It does not yet implement random parent graphs, NCH/FHS transformations,
clique expansion, demand-aware construction, traffic, or topology-performance
experiments.

## Canonical structural model

- Node and hyperedge identifiers are non-empty canonical strings.
- A structural hyperedge contains at least two unique members in canonical
  order.
- A topology stores canonical unique node and hyperedge tuples and may
  represent isolated nodes, although all deterministic anchors are connected
  and contain no isolates.
- Structural resources are exact integers:
  - node count `|V|`;
  - hyperedge count `|E|`;
  - incidence count `sum_e |e|`;
  - maximum hyperedge arity;
  - pairwise member exposure `sum_e binom(|e|, 2)`, counting an unordered
    participant pair once per shared hyperedge.

`TopologyResources` stores the canonical hyperedge-arity multiset as a
realizability witness. Hyperedge count, incidence count, maximum arity, and
pairwise member exposure are read-only derivations from that witness; callers
cannot supply mutually inconsistent aggregate values. This fail-closed shape
was added after an independent adversarial review demonstrated that validating
only loose aggregate bounds admitted impossible exposure values.

Pairwise member exposure is a structural coordination descriptor, not a fee or
measured deployment cost.

## Anchor definitions

For arity `k >= 2`, overlap `1 <= r < k`, and hyperedge count `m >= 2`, let
`s = k-r` and `n = k + (m-1)s = r + m(k-r)`.

### Sliding overlap chain

With canonical nodes `v[0],...,v[n-1]`, define

`e[j] = {v[j*s], ..., v[j*s+k-1]}` for `j=0,...,m-1`.

Thus consecutive hyperedges overlap in exactly `r` nodes. More generally,
hyperedges `d` positions apart overlap in `max(0, k-d(k-r))` nodes. This
explicit formula remains valid when `r > k/2`, where nonconsecutive edges may
also overlap; no stronger linear-hypergraph claim is made.

### Common-core sunflower

Use common core `{v[0],...,v[r-1]}`. Hyperedge `j` contains that core plus its
own disjoint block of `k-r` private nodes. Every pair of distinct hyperedges
therefore intersects in exactly the common core.

The chain and sunflower for the same `(k,r,m)` have identical node count,
hyperedge count, incidence count, arity multiset, and pairwise member exposure.

### Binary anchors and paper-1 bridge

The `k=2, r=1` special cases are an ordinary path and ordinary star. They are
the deterministic binary anchors. The `k=3, r=1` cases reproduce paper 1's
triad-chain and one-hub triad-star membership patterns after deterministic
identifier relabeling.

No cross-arity resource equality is implied by calling these binary anchors.
Resource-matched binary competitors derived from a shared parent graph belong
to the next implementation slice.

## Equal-per-node-capital initialization

Given a positive integer per-node budget `C`, each node divides `C` equally
among all incident hyperedges. Because the state engine uses exact integer
balances, initialization is accepted only when every positive node incidence
degree divides `C`; isolated nodes and indivisible budgets fail explicitly.

The resulting state must satisfy:

- every topology member appears in the corresponding state hyperedge;
- each node's balances sum exactly to `C`;
- total locked capital equals `|V| C`; and
- all balances are nonnegative integers.

Formal manifests will select budgets that are common multiples of the relevant
incidence degrees. Deterministic quotient/remainder allocation is forbidden in
the primary baseline because identifier order would otherwise create an
artificial liquidity asymmetry.

## Test-first sequence

1. Lock structural canonicalization, duplicate/unknown-member rejection,
   resource counts, and connectivity.
2. Exhaustively check small `(k,r,m)` cells against the closed-form node,
   incidence, and pairwise-overlap formulas.
3. Verify chain and sunflower resource equality in every checked cell.
4. Verify the binary path/star degree patterns and the paper-1 triad membership
   bridge.
5. Verify equal-per-node-capital sums and exact state-engine compatibility;
   reject isolated nodes and nondivisible budgets.
6. Run the complete suite on Python 3.10 and 3.12 and request a narrow
   independent structural audit before committing.

## Acceptance and claim boundary

This milestone is complete when all constructors are deterministic, structural
formulas are exhaustively cross-checked on small cells, resource equality is
explicit, initialized states preserve every node budget exactly, and an
independent reviewer reports no blocking semantic defect.

Passing this milestone establishes construction and accounting only. It makes
no claim that a chain, sunflower, binary path, or binary star has better
service reliability.
