# Demand-Aware Objective: Independent Audit

**Date:** 2026-08-01
**Decision:** PASS after one blocking API-binding repair
**Mode:** Independent read-only adversarial review

## Scope

The review independently checked the four objective terms, normalization
bounds, topology feasible set, demand/manifest/topology fingerprints, complete
score replay, and both supported Python runtimes. The reviewer did not modify
the repository.

## Blocking issue found and repaired

The first review found that the standalone
`validate_demand_aware_topology` entry point bound the parent fingerprint but
did not independently compare `manifest.node_count` with the supplied parent.
The complete scoring path already rejected that mutation, but the public
feasibility API was not consistently fail-closed.

The validator now checks the node count directly. A regression test mutating a
four-node manifest to `node_count=5` is rejected.

## Independent evidence

- An independent enumerator checked 11,135 feasible topologies for `n=2..4`.
  All four raw terms and normalized values matched the documented formulas.
- Another 50,000 random feasible topologies for `n=5..8` produced no
  participation or coordination upper-bound violation. Both normalized
  penalties have valid examples attaining exactly one.
- The reviewer checked 2,187 complete three-node demand/topology combinations;
  capture, imbalance, and both demand normalizations matched independently.
- Eight feasible-set attacks were rejected: parent binding, manifest node
  count, topology node set, incidence budget, maximum arity, induced-parent
  connectivity, parent-edge coverage, and duplicate membership.
- Collision searches covered 1,150 parents, 765 demand matrices, 823 distinct
  topologies, and 3,072 manifests without a serialization collision or omitted
  identity field.
- Eleven individual score-field forgeries plus topology-ID, demand, and
  manifest substitutions were rejected by complete objective replay.
- Ordinary Unicode fingerprints were identical on Python 3.10 and 3.12.

The repository additionally contains an independent finite-grid property test
covering 4,095 small feasible topologies. Its raw-term oracle does not call the
production scoring helpers.

## Post-audit hardening

Two nonblocking pathological-input recommendations were adopted: identifiers
must be valid UTF-8 rather than leaking `UnicodeEncodeError`, and structurally
encoded counts must fit unsigned 64-bit fields rather than leaking
`OverflowError`. Both now fail with `OptimizationError`. The immutable demand
matrix also caches its canonical values in a read-only lookup for constant-time
queries without changing equality or fingerprints.

The focused unit/property suite passes on both Python 3.10.16 and Python
3.12.13.
