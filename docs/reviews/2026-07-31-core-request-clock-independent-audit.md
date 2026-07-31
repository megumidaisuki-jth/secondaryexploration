# Independent Audit: Core Request Clock and Service Events

**Date:** 2026-07-31

**Reviewer:** Independent `metric_semantics` subagent; read-only review with no
repository modifications.

**Scope:** Composition of the verified complete router and atomic state engine
over a finite request trace; event indexing and censoring; continuation,
recovery, failure episodes, cumulative success; and adversarial validation of
manually constructed result records. Topology generation, traffic generation,
statistical estimation, and topology-performance claims were outside scope.

## Initial blocking finding

The first review found that `CoreSimulationResult` replayed accepted routes but
trusted a recorded no-path outcome. A forged result could therefore mark a
feasible request as `no_path`, retain the unchanged state, set
`tau_nopath=tau_rej=1`, and pass construction. Although the then-current test
and exhaustive-oracle suites passed, this adversarial counterexample made the
initial audit verdict **FAIL**.

## Correction and permanent regressions

Result validation now recomputes complete feasible search at every replayed
pre-state. It rejects:

- a recorded no-path outcome when any feasible route exists;
- a recorded route when complete search finds no path;
- shortest-hop, global-bottleneck, or tied-route-count metadata inconsistent
  with complete search; and
- a feasible recorded route whose own exact bottleneck does not attain the
  global optimum.

Validation deliberately does not require the recorded route to equal the
route selected by the validator's fixed random stream. Any distinct route in
the same exact optimal tie set remains valid. Permanent tests cover the false
no-path record and a feasible but globally nonoptimal recorded route. After
the independent recheck, two additional regressions were added for an
equal-hop lower-bottleneck route and acceptance of a different route in the
exact optimal tie set; these tests do not alter the reviewed production logic.

## Independent recheck

The reviewer confirmed:

- false no-path records are rejected with `SimulationError`;
- nonoptimal records are rejected through full-search metadata and exact route
  bottleneck checks;
- two different routes selected from the same optimal tie set by different
  seeds both validate successfully; and
- the reference core trace runner imports no production simulation code.

The requested focused suites passed with **17/17 tests**. The independent
integer oracle continued to match all **1,705** enumerated combinations of
small binary states and request sequences, including final balances,
acceptance sequences, all three first events and censoring flags, cumulative
success, failure episodes, recovery, and exact success rate.

After adding the two post-review regression tests described above, the final
focused suite passed **19/19 tests** and the complete repository suite passed
**94/94 tests** on both Python 3.10.16 and Python 3.12.13.

## Final verdict

**PASS - eligible for the `verified core request-clock engine` milestone.** No
blocking defect remains within the reviewed scope.

## Claim boundary

This verdict establishes the semantics of one supplied finite request trace in
the core model. It does not establish a topology-ranking result, statistical
inference, protocol sensitivity, or scientific conclusion.
