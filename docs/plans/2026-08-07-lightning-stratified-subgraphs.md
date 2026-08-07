# Lightning stratified connected-subgraph sampler

**Date:** 2026-08-07

## Purpose

Construct replayable Lightning parent graphs of sizes `30`, `60`, `120`, and
`240` from core, bridge, and peripheral structural locations. Strata and
samples are computed from the observed parent graph only. Traffic, transformed
hypergraphs, optimizer scores, and service outcomes are inaccessible to this
stage.

The four source years remain separate cross-sections. Multiple samples from
one source graph are structured subsamples, not independent observations of
the worldwide Lightning Network. Samples from different anchors may overlap
substantially and must not be treated as independent network replicates.

## Parent scope

Sampling begins from the source graph's largest connected component (LCC).
Component ties are resolved by the lexicographically smallest canonical node
tuple. Every returned sample is the induced simple graph on exactly the
selected nodes and must be connected.

## Deterministic strata

For every LCC, compute exact unweighted degree, exact core number, and exact
articulation fragmentation using standard-library integer graph algorithms.

- **Core:** the top `ceil(|V|/5)` nodes ranked by `(core number, degree,
  node id)`.
- **Peripheral:** the bottom `ceil(|V|/5)` nodes under the same ranking.
- **Bridge:** articulation vertices outside the core and peripheral pools.
  Their audit ranking records the number of components after removal and
  `|V|-1-largest fragment`, but membership does not depend on an arbitrary
  floating-point centrality threshold.

The three candidate pools are therefore mutually exclusive. A source fails
closed if any required pool is empty. The real accepted sources have adequate
bridge pools after the exclusion: 97 (2020), 406 (2022), 345 (2023), and 231
(2026).

## Anchor and growth rule

For a panel, stratum, and zero-based replicate index, derive one semantic
64-bit seed from the frozen base seed, source fingerprint, panel year, and
stratum. Hash-rank the candidate pool and assign distinct anchors to replicate
indices. No standard-library shuffle state is used.

Starting at the anchor, perform breadth-first growth. Each node's neighbors
are visited in a seed-keyed SHA-256 order. Stop when the requested size is
first reached, then return the induced graph on those nodes. The seed excludes
the requested size, so samples for sizes `30 < 60 < 120 < 240` at the same
panel/stratum/replicate form exact node-set prefixes. This provides a paired
size sensitivity, not four independent samples.

## Provenance record

Every sample records:

- source and LCC fingerprints;
- panel year, stratum, replicate index, and semantic seed;
- anchor and complete discovery order;
- requested size and induced parent graph;
- the canonical strata fingerprint, which binds the separately retained pool
  width, candidate sets, and integer node metrics;
- a canonical sample fingerprint.

The stratum label describes the anchor's role in the full source LCC. It does
not claim that the resulting induced subgraph as a whole has that label, or
that a bridge anchor remains an articulation after truncation. Rank-tail ties
are resolved by node id; overlap and boundary-tie sensitivity therefore remain
required diagnostics rather than hidden independence assumptions.

Full validation recomputes the LCC, strata, seed, anchor, discovery prefix,
induced edges, and fingerprint from the original source parent. Any mismatch
fails closed.

The batch entry point validates or computes the canonical strata record once,
then emits the complete stratum/replicate/size grid in a fixed order. This
retains fail-closed generation without repeating full-graph core and Tarjan
work for every size.

## Capital availability

All four years support equal-per-node capital. Public-capacity-derived node
totals are available only for the separately attested 2022 and RGS-v2 2026
sources. The sampler never substitutes `htlc_maximum_msat` for funding
capacity.

## Verification

- hand-audited component, core-number, and articulation fixtures;
- exact-size, connectivity, induced-edge, nested-prefix, and distinct-anchor
  tests;
- replay rejection for altered source, seed, anchor, order, or subgraph;
- real-source diagnostic counts for all four accepted years;
- full Python 3.10/3.12 repository regression before commit.
