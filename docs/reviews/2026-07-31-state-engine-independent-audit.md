# Independent Audit: Hypergraph Balance/State Engine

**Date:** 2026-07-31

**Reviewer:** Independent `metric_semantics` subagent; read-only review with no
repository modifications.

**Scope:** `secondaryexploration/model`, focused entity/transition tests, the
paper-1 unit-route bridge, and the bounded state-engine implementation
contract. Route search, request clocks, stopping times, and scientific results
were explicitly outside scope.

## Initial review

The reviewer independently classified the core implementation as PASS for:

- per-hyperedge conservation;
- feasibility checks against every payer coordinate in the pre-payment state;
- all-or-nothing route settlement;
- exact original-state identity after insufficient-balance rejection;
- exact-boundary acceptance and newly depleted payer reporting;
- continuous simple-route constraints;
- independence of one shared node's balances in different hyperedges;
- agreement with paper 1's per-hyperedge `-1/+1` unit-route definition.

The reviewer also identified one public-constructor hardening gap and four
coverage gaps. A manually constructed accepted `PaymentTransition` could name
a missing or positive-balance coordinate as depleted, even though
`apply_atomic_payment` itself never produced such an object. Tests did not yet
lock simultaneous depletion, untouched-edge identity, non-adjacent repeated
hyperedges, or the payer-not-a-member branch.

## Remediation

Before the milestone was committed:

1. `PaymentTransition` validation was extended so every reported depleted
   coordinate must exist in the post-state and have balance exactly zero.
2. Regression tests were added for the missing/positive ghost coordinates.
3. Regression tests were added for two simultaneous depleted coordinates, an
   untraversed hyperedge remaining the same object with the same balances, an
   `e1,e2,e1` route, and a payer outside the declared hyperedge.
4. The full finite exhaustive property check remained in place over 675 small
   two-edge balance/amount cases.

## Final independent verdict

The reviewer reran the latest focused suite:

```powershell
python -m unittest tests.unit.model.test_entities tests.unit.model.test_transition -v
```

Result: **34/34 passed, zero failures and zero errors.** The reviewer directly
confirmed that depleted coordinates are now checked for post-state existence
and zero balance.

Final verdict: **PASS — eligible for the `verified balance/state engine`
milestone.**

## Claim boundary

This audit validates the immutable state and one declared simple route's
atomic transition. It does not validate full feasible-path search,
`tau_dep`, `tau_nopath`, `tau_rej`, recovery, censoring, or any topology
performance claim. Those require later gates and independent audits.
