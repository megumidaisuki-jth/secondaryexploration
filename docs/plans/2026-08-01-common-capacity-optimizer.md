# Common Capacity Optimizer Contract

**Date:** 2026-08-01

**Status:** Implemented and independently audited

## Scientific role

The capacity optimizer reallocates each node's fixed integer capital among that
node's incident hyperedges. It never changes the topology, the node budgets, or
the registered training scenarios. The identical algorithm, stochastic-ticket
rule, empirical objective, and evaluation budget apply to every topology in a
primary paired comparison. A topology-specific optimizer is not permitted.

Only explicitly registered training traces enter this API. Test traces and
held-out service outcomes remain outside the manifest and are evaluated later.

## Common manifest

One manifest binds:

- the common canonical node set and amount-weighted training demand;
- the positive per-node capital budget;
- exact nonnegative load and directional-risk initializer weights;
- an exact empirical lower-quantile level; and
- canonical training scenarios, each with a regime identifier, trace, and
  request-indexed routing seed.

All traces have the same positive horizon and exactly the common node set. The
amount-weighted demand matrix must equal the aggregate of the registered
training requests. This prevents an unrecorded demand source from influencing
initialization.

## Baselines and load/risk initialization

The uniform baseline uses canonical quotient/remainder allocation and is always
evaluated. The load/risk initializer reserves one unit on every node-incidence
coordinate, then apportions the remaining node budget by exact Hamilton largest
remainders. For node `u` and incident hyperedge `e`, its positive weight is

`1 + w_load * sum_v (D_uv + D_vu) + w_risk * sum_v |D_uv - D_vu|`,

where `v` ranges over the other members of `e`. Exact rational arithmetic and
canonical hyperedge identifiers resolve every tie. Formal optimization cells
therefore require each per-node budget to be at least its incidence degree.

Both initial states are scored. The lexicographically better one starts the
refinement; a complete tie is resolved by state fingerprint. This retains the
mandatory uniform comparator without forcing an inferior demand initialization.

## Robust training objective

Every state is simulated on every registered training scenario with the same
request objects and request-indexed routing tickets. Within each regime, the
empirical lower quantile is the inverse empirical CDF order statistic
`ceil(q * m) - 1`. The primary value is the minimum regime quantile. Ties are
resolved, in order, by the sum of regime quantiles, total restricted
`tau_nopath`, total accepted requests, and then state fingerprint. Censored
traces contribute their administrative horizon as restricted event time; the
observation flag remains recorded.

The executable score retains the exact integer request index. Dividing every
candidate value by the manifest's common node count gives the prespecified
requests-per-node clock and cannot change any within-cell optimization decision;
that normalization is applied when results are compared across network sizes.

## Common projected stochastic refinement

The plan freezes the total state-evaluation budget, proposal seed, and the
number of proposals per transfer-step level. Evaluation one is uniform and
evaluation two is load/risk. Every later evaluation consumes one deterministic
ticket indexed only by the common plan and proposal index.

The ticket chooses a node and an ordered donor/recipient pair on that node's
allocation simplex. Each finite choice uses exact unsigned-64 rejection
sampling; a rejected tail ticket is extended through a versioned retry domain,
so non-power-of-two choice counts do not acquire modulo or multiplication-bin
bias. A coarse-to-fine transfer amount halves after each fixed block of
proposals and is projected onto the positive integer simplex. Degree-one nodes
or already binding donors yield an unchanged proposal, which is still evaluated
and consumes budget. Consequently every topology receives exactly the same
number of full objective evaluations. Strict lexicographic improvement is
accepted; otherwise the current state is retained. Increasing only the
evaluation budget preserves the earlier proposal and score prefix.

## Replay and verification

The result records input fingerprints, both baselines and scores, every proposal
state and score fingerprint, accepted steps, the final state, and the exact
evaluation count. Full validation receives an independently supplied expected
manifest and plan, then reruns the complete optimization.

Required verification includes exact node-capital conservation, positive
incidence balances, deterministic and cross-version replay, independent
quantile and simulation checks, small-simplex exhaustive upper bounds, budget
prefix stability, tamper rejection, and equal evaluation counts across distinct
topologies.
