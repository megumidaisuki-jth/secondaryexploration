# Independent Audit: Binary Incidence-Budget Matching

**Date:** 2026-08-01

**Reviewer:** Independent `binary_match_audit` subagent; read-only review with
no repository modifications.

**Scope:** Exact even-incidence matching, odd-incidence adjacent brackets,
parent-preserving seeded selection, stable channel identifiers, simple-graph
capacity boundaries, and public-record provenance. Capital allocation and
service outcomes were outside scope.

## Mathematical interpretation

The reviewer confirmed that a binary channel contributes two incidences.
Within the connected simple-graph capacity interval, even source budgets admit
an exact binary channel count, while odd budgets require the declared `-1/+1`
incidence bracket. The project does not assume that reliability is monotone in
this one-incidence change and does not label odd cells exact.

After review, the contract wording was tightened to make the connectivity and
simple-pair capacity conditions part of the exact-feasibility statement.

## Independent oracle

The reviewer wrote a separate SHA-256 pair-priority, Kruskal spanning-tree, and
parent-first completion oracle without importing the production matching
module. It checked **435 match cells**:

- **279** cells covering every connected labeled graph through four nodes and
  every feasible incidence budget;
- **120** cells from 24 connected five-node graphs across five budgets; and
- all **36** primary ER/BA/SBM x NCH/FHS3/FHS5 cells.

Production and oracle output agreed on every participant pair and every stable
channel identifier. The audit independently confirmed:

- exact even budgets and `-1/+1` odd brackets;
- `lower subset upper` nesting;
- parent-only selection when the target does not exceed the parent edge count;
- retention of every parent edge when the target exceeds it;
- exact parent-membership reproduction at equal edge count;
- simple connected outputs with the complete node set; and
- identifiers derived from canonical node indices.

## Adversarial and test evidence

The reviewer confirmed fail-closed handling for altered source budgets, root
seeds, lower brackets, negative seeds, Boolean budgets, node mismatches,
disconnected parents, connectivity-short budgets, and targets beyond simple
pair capacity. Because the record recomputes both outputs, altered upper
brackets, pair sets, and bracket order are also rejected.

The focused suite passed **8/8 tests** under Python 3.10.16 and Python 3.12.13:
six unit, one exhaustive property, and one integration test. The repository
property test separately covers **9,743** small-graph match cells. The complete
repository suite passed **150/150 tests** under both Python versions, and both
bytecode compilation checks passed.

The reviewer suggested explicit tests for upper-bracket forgery and unsigned
64-bit seed overflow. Those cases were added after the read-only audit and the
focused suite passed again under both Python versions.

## Final verdict

**PASS - eligible for the verified binary incidence-budget matching
milestone.** No blocking defect was found.

## Claim boundary

This audit verifies structural budget matching and deterministic selection. It
does not establish a performance ordering, a uniform spanning-tree sample, or
an exact cost match for odd source incidence. Odd cells remain adjacent-budget
sensitivity analyses; strict confirmatory matching uses feasible even budgets.
