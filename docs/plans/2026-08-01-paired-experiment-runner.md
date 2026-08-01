# Paired experiment runner contract

## Purpose

Run every topology derived from one parent-graph block against the exact same
request trace and request-indexed route-choice randomness.  The runner must
preserve the paired experimental unit and make every scientific input part of
an immutable, fingerprinted manifest.

## Locked pairing unit

One `PairedRunManifest` contains:

- one block identifier;
- one replay-attested `RequestTrace`;
- one unsigned 64-bit routing root seed; and
- a canonical tuple of topology variants, each with an exact structural
  topology and initial balance state.

All variants must use the same canonical node set, the trace kernel must use
that node set, and every variant must have identical per-node initial capital.
Each initial state must reproduce the topology's hyperedge identifiers and
members exactly.  Variant identifiers are unique and canonically ordered.

## Common route-choice tickets

Request `i` receives one unsigned 64-bit leading ticket derived from
`(routing_root_seed, "routing.ticket", i)`.  It is interpreted as the first
64 bits of a shared binary quantile `U` in `[0, 1)`.  For `m` tied optimal
routes, the selected zero-based route ticket is

`floor(U * m)`.

The implementation first asks whether the leading 64-bit interval lies wholly
inside one of the `m` equal bins.  If it straddles a bin boundary, or if `m` is
larger than `2**64`, deterministic SHA-256-derived 64-bit extension blocks
refine the same computational pseudorandom interval until one bin remains.

The distinction between the ideal-bit model and the executable finite-seed
family is explicit.  Independent uniform infinite bits would give every bin
probability exactly `1/m`.  The implementation is instead a deterministic PRF
construction keyed ultimately by a 64-bit root seed: it has at most `2**64`
possible streams, cannot give literal full support when `m > 2**64`, and need
not divide a finite seed ensemble into exactly equal bin counts.  Over the
uniform domain of all 64-bit leading tickets, for `m=3`, the independently
audited maximum absolute probability discrepancy and total variation distance
are both `2 / (3 * 2**64)`, approximately `3.61e-20`.
Claims and statistical interpretation use computational pseudorandomness, not
an unconditional infinite-entropy assertion.

Thus all variants use the same extensible pseudorandom quantile for the same
request index.
The mapping is independent of whether earlier requests had zero, one, or many
optimal routes, so topology-dependent RNG consumption cannot desynchronize a
paired block.

## Manifest identity

The manifest fingerprint is SHA-256 over canonical UTF-8 JSON containing the
schema version, block identifier, routing seed, complete traffic and amount
weight tables, trace seed and length, exact generated requests, and every
variant's topology and initial balances.  Changing any scientific input must
change the fingerprint.

## Result invariants

A `PairedRunResult` must:

- contain exactly one result for every manifest variant in canonical order;
- reuse the manifest request objects without regeneration;
- preserve each declared initial state and common horizon; and
- replay every selected route exactly with the request-indexed shared ticket.

The result constructor rejects records that are merely feasible but do not
match the declared common-ticket route choice.

## Verification

Tests cover known ticket vectors, quantile bounds, independence from earlier
tie consumption, manifest structural/capital/trace rejection, fingerprint
sensitivity, exact result replay, and an end-to-end paired run on distinct
hypergraphs.  Both supported Python runtimes run the focused and full suites;
an independent read-only audit is recorded before the milestone is committed.
