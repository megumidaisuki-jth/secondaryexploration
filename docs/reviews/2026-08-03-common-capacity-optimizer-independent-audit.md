# Common Capacity Optimizer Independent Audit

**Date:** 2026-08-03

**Verdict:** PASS

**Scope:** Read-only independent audit of the common fixed-node-capital
initializer, robust training objective, projected stochastic refinement, and
complete replay validator. The reviewer made no repository modifications.

## Input and initializer audit

The manifest fingerprint binds canonical nodes, the amount-weighted aggregate
training demand, per-node capital, exact load/risk weights, exact lower-quantile
level, and every scenario. Scenario fingerprints include the demand kernel,
amount table, traffic root seed, complete request tuple, and request-indexed
routing seed. The public training, scoring, and optimization APIs accept no
held-out outcome or test-result parameter.

An independent Hamilton apportionment implementation matched all 10,000 random
initializer cases. Every allocation retained at least one unit on each
incidence, conserved the exact budget of every node, and resolved equal
remainders by canonical hyperedge identifier.

## Robust objective audit

An independent empirical inverse-CDF grid reproduced the registered
`ceil(q*m)-1` order statistic. Scenario outcomes are grouped by regime; the
comparison key then maximizes the minimum regime quantile, sum of regime
quantiles, total restricted `tau_nopath`, and accepted-request total, in that
order. State fingerprint is the final deterministic tie break. A censored run
contributes its administrative horizon as restricted time while retaining its
observation flag.

The exact oracle no longer calls the production capacity scoring function. It
enumerates the complete Cartesian product of positive integer node-simplex
allocations for ten fixed-seed random connected graphs with three or four nodes,
runs the simulator independently, and computes the quantile and maximin key by
hand. It also retains a three-state anchor on which the search reaches the
independent global optimum.

## Search fairness and replay

Eighty random connected topologies confirmed that increasing the evaluation
budget from six to eleven preserves the complete earlier proposal-and-score
prefix. Every topology consumes the exact common evaluation count. Ordered
donor/recipient selection covers `d*(d-1)` choices, the coarse-to-fine step
halves by fixed proposal blocks, and projection clips the donor at one positive
unit while preserving the node simplex.

Non-power-of-two choices use an unsigned-64 rejection limit followed by a
versioned retry domain. This removed an earlier multiplication-bin bias found
during review. The reviewer independently verified the rejection boundary and
ordered-pair mapping.

Eight tamper classes were rejected by complete replay: result-manifest changes,
a complete valid result from an alternate plan, manifest quantile changes,
scenario routing-seed changes, coordinated state/score substitutions, proposal
metadata changes, proposal outcome/score changes, and accepted-step changes.

## Runtime verification

The focused capacity suite passed **15/15 tests** under Python 3.10.16 and
Python 3.12.13. The full repository passed **257/257 tests** under both
interpreters. A 3,735-byte complete result record was identical across versions;
both compile passes and the whitespace check succeeded.

Two limitations remain explicit and non-blocking. The stochastic refinement is
a fixed-budget heuristic and, outside the registered small anchor, does not
claim global optimality. Formal-scale capacity-optimization wall-clock
benchmarking remains part of experiment-manifest construction rather than this
contract-level audit.
