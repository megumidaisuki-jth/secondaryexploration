# Study Design Manifest and Seed Ledger

**Date:** 2026-08-03

**Status:** Implemented and independently audited

## Purpose and phase boundary

The study manifest freezes the complete experiment matrix before any result is
interpreted. It distinguishes three phases:

- `pilot`: non-confirmatory runtime, coverage, and variance estimation;
- `formal`: a configuration whose parent count and precision targets are frozen
  from an identified pilot evidence artifact; and
- `confirmation`: an independent rerun based on a formal artifact and a
  disjoint root-seed family.

A pilot manifest cannot be relabeled formal. Formal and confirmation manifests
must bind a basis fingerprint, code revision, and environment-lock fingerprint.
No result-dependent field or stopping decision is accepted by the schema.

## Synthetic matrix

Every size cell declares node count, BA attachment count, community-block count,
and exact SBM within-edge count. The BA identity fixes the shared parent edge
count as `a(n-a)`; ER and SBM use that exact count. Pilot sizes must be a
nonempty subset of `{30, 60, 120, 240}`. Formal and confirmation phases require
all four primary sizes.

The manifest also freezes parent count, resampling ceiling, requests per node,
training and test trace counts, per-node capital, exact amount/weight table,
primary FHS arities, four rational topology-objective coefficients, topology
search budget, capacity search budget, and robust lower-quantile level.
The executable topology registry is frozen as NCH, FHS3, FHS5, and the
demand-aware family, with FHS5 declared as the demand-aware search seed.

## Traffic registry

The training registry contains exactly one uniform, community-local,
exogenous-hotspot, and directional-drift regime. Test entries must reference a
training regime and declare one of four relationships:

1. exact same-distribution parameters;
2. disjoint canonical hotspot relocation;
3. exact forward/reverse directional-weight reversal; or
4. strictly increased cross-community weight with unchanged within weight.

Every training regime requires a same-distribution test entry. The three shift
types must also be present. Hotspot nodes, community blocks, and directional
groups are derived only from canonical node indices and the manifest parameters,
never from topology centrality or held-out outcomes.

## Seed ledger

The root seed is separated by phase, size, parent replicate, split, regime, and
trace replicate. One trace seed and one request-indexed routing seed are shared
across ER, BA, and SBM topology variants inside the matched block. Training and
test namespaces are disjoint. The finite ledger fails closed if any generated
64-bit seed collides.

The ledger records every parent-ensemble seed and every traffic/routing seed,
has its own structurally framed SHA-256 fingerprint, and regenerates completely
from the manifest. Increasing a later trace count cannot silently reassign an
earlier semantic seed because derivation uses named fields rather than a single
sequential RNG stream.

## Verification

- strict JSON rejects duplicate, missing, unknown, non-UTF-8, and malformed
  nested fields;
- phase, size, resource, regime-reference, and shift invariants fail closed;
- canonical JSON and fingerprints are stable across Python 3.10 and 3.12;
- regenerated ER/BA/SBM ensembles exactly match node and edge resources;
- generated trace objects match the declared kernel, amount table, horizon,
  split, and seed;
- training/test and parent/traffic/routing seeds are unique in the finite
ledger; and
- tampered manifests, ledgers, parameters, or records fail complete replay.

## Train-once parent-block pipeline

For each registered parent draw, the pipeline aggregates only the four
training regimes into one amount-weighted directed-demand matrix. It constructs
the four declared hypergraph families, trains the demand-aware topology from
the frozen FHS5 seed, and deduplicates resource-matched binary comparators by
their exact incidence identity. Every unique service topology receives the
same capacity manifest, search plan, and evaluation budget. Clique expansions
are retained only as infrastructure-cost references and are never added as
duplicate service competitors.

The trained topology and capacity states are then frozen before the seven
held-out traces run. Every held-out paired run reuses the same request objects
and request-indexed routing-ticket family across all variants. The versioned
parent-block fingerprint binds full parent provenance, training and held-out
seed records, demand-aware score and proposal history, topology structures,
capacity optimization records, resource panels, clique references, routes,
states, and event times. Complete replay rejects any altered record.

## Frozen pilot identity and audit

- manifest SHA-256:
  `ffcdffe43e3d77b978e4a64cc2aaa368c302fe63cce92f4e6f16ad415625fb4c`;
- seed-ledger SHA-256:
  `284928d1a3f4679ac373f45984fb006622d88e085f0be95cb418fcf7a599988d`;
- tracked pilot sizes: 30 and 60 nodes, one matched parent replicate each;
- registered traffic: four training, four same-distribution test, and three
  shifted test regimes; and
- independently verified on Python 3.10 and 3.12 with 267/267 repository tests
  per interpreter, byte-identical canonical identities, and successful
  compilation.

Formal and confirmation manifests remain deliberately unfrozen. Their parent
and trace counts will be chosen from a separately identified pilot evidence
artifact, whose existence and precision rationale must be checked by the later
freeze workflow rather than inferred from this schema alone.
