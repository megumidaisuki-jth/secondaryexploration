# Independent Audit: Deterministic Topology Anchors

**Date:** 2026-07-31

**Reviewer:** Independent `metric_semantics` subagent; read-only review with no
repository modifications.

**Scope:** Balance-free topology invariants, sliding overlap-chain and
common-core sunflower formulas, structural resource accounting, paper-1 and
binary anchor bridges, equal-per-node-capital initialization, and integration
with the verified router, state engine, and request clock. Random topology
generation and topology-performance claims were outside scope.

## Initial blocking finding

The anchor memberships and capital allocation passed the first review, but the
public aggregate `TopologyResources` constructor admitted impossible resource
tuples. In particular, a topology with one three-member hyperedge could be
manually recorded with pairwise member exposure `1` or `999`, although the only
valid value is `binom(3,2)=3`. Normal `topology.resources` derivation was
correct, but the public value object was not fail-closed, so the initial audit
verdict was **FAIL**.

## Correction

`TopologyResources` now stores only:

- a positive exact node count; and
- a canonical tuple containing every hyperedge arity.

Each arity must be an integer between two and the node count. Hyperedge count,
incidence count, maximum arity, and pairwise member exposure are read-only
derivations from this realizability witness. Because parallel structural
hyperedges are permitted, every accepted arity tuple is realizable, while a
caller can no longer inject inconsistent aggregate values. Permanent tests
cover the original triad counterexample plus non-tuple, noncanonical, noninteger,
and out-of-range arity witnesses.

## Independent recheck

The reviewer confirmed:

- the former exposure `1` and `999` counterexamples are rejected;
- three valid witnesses produce the exact four derived resource values;
- eleven adversarial resource inputs are rejected;
- no call site retains the superseded aggregate constructor;
- all `75` cells with `k=2..6`, every `r=1..k-1`, and `m=2..6` satisfy the
  closed-form resource and overlap contracts;
- those cells contain `150` independently checked chain/sunflower anchors,
  including `30` cells with `r>k/2`;
- all `525` pairwise chain intersections and `525` pairwise sunflower
  intersections match their declared formulas;
- the binary path/star and paper-1 triad bridges are exact; and
- all `150` checked equal-capital states preserve every node budget without
  quotient/remainder identifier bias.

The final topology-focused suite passed **20/20 tests**: 18 unit tests, one
exhaustive property test, and one cross-module integration test. The complete
repository suite passed **114/114 tests** on Python 3.10.16 and Python 3.12.13.

## Final verdict

**PASS - eligible for the `verified deterministic topology anchors`
milestone.** No blocking defect remains within the reviewed scope.

## Claim boundary

This verdict establishes deterministic construction, exact resource
accounting, and capital initialization. It does not show that any anchor family
has superior survival, availability, recovery, cost, or deployability.
