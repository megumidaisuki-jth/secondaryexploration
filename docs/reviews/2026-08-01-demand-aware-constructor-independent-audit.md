# Demand-Aware Constructor Independent Audit

**Date:** 2026-08-01

**Verdict:** PASS

**Scope:** Read-only independent audit of the deterministic connected-candidate
generator and fixed-incidence demand-aware topology search. The reviewer made
no repository modifications.

## Candidate generation

For every connected parent graph through five nodes and every admissible
maximum arity, 3,035 generated pools exactly matched an independent enumeration
of all parent-induced connected subsets. A further 300 random cases with six
through ten nodes also matched. For 120 random cases above the exhaustive
threshold, the reviewer independently reproduced canonical and demand-priority
expansions, exact rational priorities, connectivity, complete parent-edge
coverage, de-duplication, ordering, and deterministic replay.

## Move stream and compute budget

For 1,500 random inputs, the production move stream matched an independent
enumeration of every equal-incidence removed-by-added class up to three edges
on each side. The comparison included 26,881 proposals containing duplicate
memberships: each such structurally distinct infeasible proposal was recorded
and consumed budget before rejection. Dynamic-programming arity pruning omitted
no reachable class, and every emitted proposal preserved total incidence.

One hundred independent proposal-by-proposal replays exactly reproduced the
proposal fingerprints, feasible-evaluation totals, accepted-step intervals,
strict-best-improvement decisions, and topology-fingerprint tie breaks. Two
hundred one-round checks confirmed that increasing the common proposal budget
preserves the previously observed proposal prefix.

## Feasibility and optimality checks

The seed, every scored proposal, every accepted step, and the final topology
pass the complete registered feasible-set validator. Independent scans found no
way to bypass the node-set, incidence-budget, maximum-arity, induced-
connectivity, parent-edge-coverage, duplicate-membership, or global topology
constraints.

The registered Path4 and Path5 cases reached their independently enumerated
global optima. Eighty additional random four-node cases also reached their
independent global upper bounds. These small-graph results validate the
registered oracle cases; they do not turn the formal-size bounded heuristic
into a claim of global optimality.

## Replay and tamper resistance

The reviewer altered candidate priorities and inputs, the manifest, seed,
candidate pool, proposal record, feasible count, step record, final topology,
and score. Full replay rejected every alteration. It also rejected a complete,
internally valid result produced under a different search plan because
validation requires the separately supplied expected plan.

The immutable demand caches preserved the four existing golden fingerprints
byte for byte. Five hundred random demand matrices reproduced independently
computed lookup values, bidirectional totals, and directional-imbalance totals.

## Runtime verification

The latest focused suite passed **14/14 tests** under both Python 3.10.16 and
Python 3.12.13. An independent 240-node path smoke run generated 950 candidates
and evaluated 100 proposals, of which three were feasible, while preserving the
478-incidence budget; elapsed time was approximately 1.02 seconds.

The only residual limitation is the one declared in the contract: above ten
nodes, candidate generation and the fixed-budget local search are bounded
heuristics and do not provide a global-optimality guarantee. This is a research
scope limitation, not an implementation defect.
