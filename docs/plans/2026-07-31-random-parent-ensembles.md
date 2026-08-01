# Matched Random Parent-Graph Ensemble Contract

**Date:** 2026-07-31

**Milestone:** Reproducible connected Erdős-Rényi, Barabási-Albert, and
fixed-count stochastic-block parent graphs with exact within-block resource
matching.

## Scope and claim boundary

This slice generates balance-free parent graphs only. It does not allocate
capital, generate payment traffic, estimate service reliability, or claim
that any graph family is empirically superior. The incidence-matched binary
payment-network selector remains a separate follow-on slice.

## Common node and edge contract

- Every graph uses the canonical node identifiers `v00000000`, ...,
  `v{n-1:08d}`.
- Within one matched ensemble, ER, BA, and SBM use exactly the same node set,
  edge count, and therefore exact rational mean degree.
- Every accepted graph is simple, undirected, and connected.
- Primary sizes remain `n in {30, 60, 120, 240}`. The implementation also
  supports smaller audit instances.

## Frozen graph families

### Connected fixed-edge ER

An ER attempt samples exactly `m` unordered pairs uniformly without
replacement from all `choose(n,2)` pairs. Disconnected attempts are rejected.
This is the connected conditional form of `G(n,m)`, not independent-edge
`G(n,p)`.

### Fixed-edge BA

For attachment count `a`, initialize a star on nodes `0,...,a` with node zero
as center. Add each later node in canonical order and connect it to `a`
distinct existing nodes selected from a degree-proportional repeated-node
multiset. Duplicate targets within one arrival are redrawn. Selected targets
are appended to the multiset in canonical order.

The graph is connected by construction and has exactly `a(n-a)` edges. That
edge count is the common target for ER and SBM in the matched builder. The
initialization and tie/order rules are part of the model definition; results
must not be described as invariant to alternative BA implementations.

### Connected fixed-count SBM

Nodes are assigned to declared non-empty blocks in canonical contiguous order.
Each attempt independently samples the declared number of within-block pairs
and the remaining number of between-block pairs, uniformly without
replacement inside each pool. Disconnected attempts are rejected. This is a
microcanonical fixed-count stochastic-block ensemble, not an independent-edge
Bernoulli SBM.

## Stable randomness and resampling

- A graph-family root seed is an unsigned 64-bit value.
- Attempt `j` uses
  `derive_seed(root_seed, "parent.<family>.attempt", j)`.
- Attempts are zero-based. The accepted attempt index, root seed, and derived
  draw seed are exposed in an immutable record.
- Candidate pairs are canonical. Sampling uses a project-owned partial
  Fisher-Yates routine and an unbiased `getrandbits` rejection sampler, so no
  standard-library collection iteration order enters the result.
- `max_attempts` must lie in `[1,10000]`. Exhaustion raises a typed topology
  generation error; it never silently changes the edge budget or returns a
  disconnected graph.
- A draw record is an attestation rather than an unchecked label: construction
  replays its declared model parameters and seed, checks that the stored edge
  set is exact, and confirms that every earlier ER/SBM attempt was rejected.
  BA records can only use attempt zero.

## Matched ensemble builder

For `(base_seed, replicate_index)` the builder derives disjoint ER, BA, and
SBM root seeds. It validates the BA attachment count, the exact SBM within-edge
count, block capacities, and the necessary number of between-block edges.
The returned record rejects any mismatch in node mapping, edge count, mean
degree, connectivity, or block partition.

## Verification gates

1. Known seeded edge-set vectors freeze each family's semantics.
2. Replay tests freeze accepted attempt indices and derived seeds.
3. Invalid, impossible, and exhausted draws fail closed.
4. Property grids verify simplicity, connectedness, exact counts, fixed SBM
   within/between counts, and cross-family matching.
5. Every primary network size receives at least one deterministic smoke draw.
6. Python 3.10 and 3.12 must pass the complete suite before commit.
7. A read-only independent audit must use a separately written oracle for the
   seeded draw and matching invariants.
