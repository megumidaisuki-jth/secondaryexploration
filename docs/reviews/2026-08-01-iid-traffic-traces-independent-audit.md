# Independent Audit: IID Traffic Kernels and Request Traces

**Date:** 2026-08-01

**Reviewer:** Independent `traffic_trace_audit` subagent; read-only review with
no repository modifications.

**Scope:** Exact integer-weight uniform, community-local, exogenous-hotspot,
and directional-drift kernels; integer-weight amount distributions; separated
random streams; and replay-attested `PaymentRequest` traces. Temporal
dependence, pilot amount calibration, and paired experiment execution were
outside scope.

## Independent oracle

The reviewer used a standalone process that did not import the production
traffic package. It independently implemented the versioned SHA-256 seed
derivation, `Random.getrandbits` rejection sampler, four kernel formulas, and
integer ticket maps.

The oracle confirmed:

- four complete ordered-pair weight tables, exact total weights, and every
  ticket multiplicity;
- **96** trace cells covering four kernels, eight seeds, and three lengths;
- exact equality of all **288** independently generated requests;
- the frozen eight-request golden vector and both derived stream seeds;
- endpoint invariance under amount-table changes and amount invariance under
  kernel changes; and
- exact full support with distinct source and destination in every request.

## Adversarial evidence

The audit exercised **22** malformed or forged cases covering missing pairs,
duplicate pairs, self-pairs, zero or Boolean weights, invalid community,
hotspot, and directional partitions, seed and length boundaries, and altered
request content, order, seed, or declared length. Every case failed closed.

The focused suite passed **15/15 tests** under both Python 3.10.16 and Python
3.12.13: 13 unit, one finite property grid, and one integration test. The
integration test passes the same request objects through structurally distinct
overlap-chain and common-core-sunflower networks.

## Final verdict

**PASS - eligible for the verified iid traffic and amount-trace milestone.**
No blocking or non-blocking defect was reported.

## Claim boundary

This audit verifies exact relative weights, deterministic iid sampling, stream
separation, and trace reuse. The weights are not empirical rates, and no
reliability effect, temporal-dependence result, or amount-stress calibration is
established by this milestone.
