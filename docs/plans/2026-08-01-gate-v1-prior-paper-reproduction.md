# Gate V1: Prior-Paper Semantic Reproduction

**Date:** 2026-08-01
**Status:** Passed after independent audit
**Scope:** Uploaded HPN paper and its public 2022 Lightning inputs

## Purpose

Gate V1 tests whether the paper-2 implementation can recover the published
direction of the NCH/FHS structural, shortest-available-path, success-rate, and
path-length findings before any new formal experiment is allowed to start.
Exact numerical identity is not required because the paper does not publish its
NCH/FHS simulator and the public repository contains only the Lightning input,
traffic trace, and traffic-generator dependency.

## Frozen semantic layers

1. The primary paper-2 router remains the full balance-aware policy:
   shortest feasible hop count, then maximum normalized post-payment
   bottleneck, then reproducible uniform tie-breaking.
2. Gate V1 uses a separate uniform shortest-available-path router. It searches
   the complete current residual hypergraph but does not prefer the route with
   the largest balance margin.
3. A second balance-independent uniform shortest-path router is retained only
   as the bridge to paper 1. It chooses from the static topology before
   settlement feasibility is considered.
4. Results produced by these policies use distinct result types and validators.
   A Gate-V1 comparison result carries topology, initial-state, and request-trace
   fingerprints; its explicit validator binds those inputs and completely
   re-executes the comparison policy. It cannot validate as a primary
   balance-aware result.

## Source interpretations to record

- NCH uses closed neighborhoods `{c} union N(c)`. This corrects the uploaded
  paper's literal open-neighborhood pseudocode, which omits the cover node and
  can produce orphan nodes or one-member channels.
- FHS counts the maximum-degree seed among the `m_max` total BFS nodes and uses
  canonical identifier tie-breaking.
- Each published Lightning channel capacity is split equally between its two
  endpoints. A transformed topology preserves each node's resulting total
  capital and divides it deterministically among that node's incidences.
- A hyperedge traversal counts as one hop irrespective of arity.
- Gate V1 uses the published 10,000-request endpoint trace and its fixed 60,000
  SAT amount. Requests whose endpoints do not survive the declared graph
  filter remain in the success-rate denominator as explicit unavailable-node
  failures, matching the accessible upstream simulator instead of silently
  deleting them.

The active-channel rule is now data-identified: retain a channel when at least
one directional policy exists and is not disabled, then collapse parallel
channels for the structural parent graph. On public commit
`2c4ffc92d704fa1b043fac395c1e5f662990d497`, this yields exactly 11,268
non-isolated nodes and 61,966 simple edges. Consequently `2E/N = 10.99858` is
close to the paper's reported (truncated) average degree 10.99, and two L1
transactions per binary
channel at `w_c=3` reproduce the reported construction cost exactly:
`2 * (2E) * 3 = 743,592`.

This anchor-matching filter is not the public dependency's preprocessing rule.
That dependency first requires both directional policies and can also discard
channels below the payment amount. The exact graph-size consequences are part
of the discrepancy ledger, so the Gate is a declared source interpretation,
not a claim to rerun the dependency unchanged.

## Evidence stages

1. Audit the PDF, public repository commit, input hashes, and accessible code.
2. Implement and exhaustively test the two isolated comparison routers.
3. Import the public 2022 graph and trace with a hash-attested manifest.
4. Produce LN, NCH, and registered FHS structural descriptors.
5. Replay the common trace under uniform shortest-available-path routing.
6. Compare only directional findings: hyperedge arity/count, successful-path
   length, success rate under amount stress, and capital required for a common
   fixed-horizon success target.
7. Write a discrepancy ledger. Every difference must be explained by source
   ambiguity, unavailable implementation, dependency version, corrected
   pseudocode, filtering, tie-breaking, initialization, or Monte Carlo error.
8. Obtain independent audit before declaring Gate V1 passed.

## Blocking rule

Formal paper-2 experiments remain blocked if the published direction cannot be
reconciled under at least one declared faithful source interpretation. A
direction recovered only after undisclosed tuning does not pass Gate V1.
