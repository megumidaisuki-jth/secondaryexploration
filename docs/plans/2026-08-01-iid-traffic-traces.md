# Reproducible IID Traffic and Amount Trace Contract

**Date:** 2026-08-01

**Milestone:** Exact integer-weight demand kernels, amount distributions, and
replay-attested request traces for paired experiments.

## Scope

This slice implements the four primary i.i.d. request kernels and exact integer
amount sampling. Markov-modulated hotspots, burst processes, heavy-tail amount
mixtures tied to a final pilot, and experiment execution belong to later
slices.

## Authoritative weighted tables

A demand kernel is an immutable canonical table containing every ordered pair
of distinct nodes exactly once with a positive integer weight. Integer weights
avoid platform-dependent floating-point normalization and guarantee full
source-destination support.

The four constructors are:

1. **Uniform:** every ordered pair has weight one.
2. **Community-local:** declared non-empty blocks form a canonical partition of
   the node set; within-block and cross-block pairs receive separate positive
   integer weights.
3. **Exogenous hotspot:** a declared non-empty proper subset contains the
   hotspot labels. A pair's base weight is multiplied once for each hotspot
   endpoint, so two hotspot endpoints receive the squared multiplier. Labels
   are input data and are never selected from topology degree or centrality.
4. **Directional drift:** two declared non-empty groups partition the nodes.
   Left-to-right, right-to-left, and within-group ordered pairs receive three
   separate positive integer weights.

The complete weight table, not a family label, is authoritative. It exposes a
canonical SHA-256 fingerprint and exact ticket-to-pair mapping.

An amount distribution is the analogous canonical positive-integer table over
distinct positive integer payment amounts. Fixed small/medium/large workloads
are one-point distributions; later mixtures use the same object.

## Stable sampling and stream separation

For a trace root seed:

- ordered-pair draws use `derive_seed(root_seed, "traffic.pairs", 0)`;
- amount draws use `derive_seed(root_seed, "traffic.amounts", 0)`.

Each i.i.d. draw uses an unbiased `getrandbits` rejection sampler over the
table's total integer weight. Separate streams guarantee that changing the
amount distribution leaves the endpoint sequence unchanged and changing the
demand kernel leaves the amount sequence unchanged, provided trace length and
root seed stay fixed.

## Request trace attestation

`RequestTrace` stores the kernel, amount distribution, root seed, and canonical
`PaymentRequest` tuple. Public construction replays both streams and rejects an
altered request, length, endpoint, amount, order, or seed. Every request uses a
node in the kernel and has distinct endpoints.

The exact request tuple is passed unchanged to every topology in a pairing
block. Routing tie randomness is a different experiment stream and is not
consumed during traffic generation.

## Claim boundary

Integer weights define relative probabilities; they do not represent observed
payment rates unless a dataset and calibration manifest explicitly establish
that interpretation. This slice proves replay and kernel semantics, not
service-reliability effects.

## Verification gates

1. Exact table counts, totals, and ticket maps for all four kernels.
2. Known fingerprints and seeded request vectors.
3. Endpoint/amount stream-separation metamorphic tests.
4. Invalid partitions, hotspots, weights, amounts, seeds, and forged traces
   fail closed.
5. Finite seed/length grids replay exactly on both supported Python versions.
6. A generated trace runs unchanged through at least two structurally distinct
   payment topologies.
7. The complete suite and an independent read-only audit pass before commit.
