# Demand-Aware HPN: Deterministic Candidate and Search Contract

**Date:** 2026-08-01
**Status:** Implemented and independently audited

## Role of the constructor

The constructor trains one topology from a registered feasible seed topology,
the training-only amount-weighted demand matrix, and the independently audited
four-term objective. The seed is a demand-blind topology produced before test
traces exist. Its exact identity is retained, so the trained topology can be
compared both with other families and with its own structural initializer.

The search never changes the manifest's node set, total incidence budget, or
maximum arity. Every proposed topology is passed through the complete feasible
set validator before it can be scored. Held-out requests and service outcomes
are absent from the API.

## Connected candidate pool

Candidate memberships are deterministic connected subsets of the parent graph.

- For `n <= 10`, enumerate every parent-connected subset with arity from two
  through the registered maximum. This enables exhaustive small-graph oracles.
- For larger graphs, include every parent edge, then generate canonical and
  demand-prioritized connected expansions from every node and every parent
  edge through the maximum arity.
- Demand-prioritized expansion adds the frontier node with the greatest exact
  marginal bidirectional-capture reward minus directional-imbalance penalty;
  ties use canonical node identifiers.
- Duplicate member sets are removed.

Candidate priority is only a deterministic proposal-order heuristic. The
accepted move is always selected using the complete registered topology
objective, never the standalone candidate score.

The pool records the generator version, manifest fingerprint, every canonical
membership, and its exact rational priority. A validator regenerates the pool
from the bound inputs.

## Fixed-resource local moves

One search round interleaves the following proposal classes:

1. replace one hyperedge by one candidate of equal arity;
2. split one hyperedge into two candidates whose arities sum to the removed
   arity;
3. merge two hyperedges into one candidate whose arity equals their summed
   arity; and
4. replace two hyperedges by two candidates with the same total incidence.

The same equal-incidence rule is generalized to every registered
`removed_count x added_count` class up to three edges on each side. This is
necessary at maximum arity three, where changing three binary channels into
two triadic channels cannot be expressed by a two-edge move.

Thus the search can alter memberships, arity distribution, and hyperedge count
without changing total incidence. Proposals with duplicate memberships or any
feasibility violation are rejected. The four generators are consumed in
round-robin order so a finite budget cannot silently exclude split/merge moves
behind a much larger one-for-one neighborhood.

## Deterministic bounded optimization

A search plan freezes the candidate/search versions, maximum move width,
global proposal budget, and maximum number of improving rounds. Every distinct
proposal, including an infeasible one, consumes budget. Within a round, the
feasible strict improvement with the
largest exact objective is retained; objective ties use the canonical topology
fingerprint. If no strict improvement exists, training stops. There is no
stochastic state and no topology-specific search budget.

The result records the seed, pool, plan, proposals considered, feasible scores,
accepted steps, final topology, and final exact score. Full validation
first compares the result with a separately supplied frozen search plan, then
regenerates the pool and reruns the entire search. The algorithm is a declared
bounded heuristic, not a claim of global optimality on formal-size graphs.

## Verification requirements

- small graphs: candidate pool equals exhaustive connected-subset enumeration;
- every accepted and final topology satisfies the complete feasible set;
- exact incidence and arity limits hold after all four move classes;
- increasing a proposal budget preserves the already-enumerated proposal
  prefix within the same round;
- repeated runs and Python 3.10/3.12 produce identical records;
- a separate exhaustive feasible-topology oracle bounds or matches the search
  on registered small cases;
- result, step, pool, or plan tampering fails full replay.
