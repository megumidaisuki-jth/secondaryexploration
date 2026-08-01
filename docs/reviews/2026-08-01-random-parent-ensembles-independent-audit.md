# Independent Audit: Matched Random Parent-Graph Ensembles

**Date:** 2026-08-01

**Reviewer:** Independent `random_graph_reaudit` subagent; read-only review
with no repository modifications.

**Scope:** Connected fixed-edge ER, frozen star-initialized BA, connected
fixed-count SBM, resampling metadata, model/seed provenance, and exact
cross-family node/edge/mean-degree matching. Payment-topology resource matching
and service outcomes were outside scope.

## Initial failure and repair

An earlier independent audit rejected the first implementation because a
public `ParentGraphDraw` accepted `accepted_attempt=2**64` and failed only when
its `draw_seed` property was read. The same unchecked-label design admitted BA
records with impossible nonzero attempts and graphs unrelated to their stated
model seed.

The repaired record now:

- restricts attempts to integer indices in `[0,10000)`;
- requires at least two canonical `v########` nodes;
- restricts BA to attempt zero and records its attachment count;
- records fixed-count SBM blocks and within-edge count;
- reconstructs the complete edge set from the declared model parameters and
  derived draw seed;
- proves every earlier ER/SBM attempt was disconnected; and
- verifies that matched ER/BA/SBM roots derive from the declared
  `(base_seed, replicate_index)` under three separate namespaces.

## Independent checks

The bounded re-audit confirmed:

- rejection of five invalid attempt values: `-1`, `10000`, `2**64`, `True`,
  and `1.0`;
- rejection of nine BA forgeries covering nonzero attempts, fake model types,
  noncanonical or singleton nodes, missing/wrong parameters, foreign SBM
  parameters, wrong root seeds, and wrong edge sets;
- independent reproduction of six ER and six SBM small-grid draws, including
  exact accepted edge sets and proof that every preceding attempt was
  disconnected;
- exact ER, BA, and SBM root-seed derivation plus rejection of altered base
  seeds and replicate indices; and
- all four primary sizes `n in {30,60,120,240}` use the same nodes, exact edge
  count, and exact rational mean degree within their three-family block.

The independent small-grid accepted attempts were
`(0,0,0,0,5,0,0,0,0,0,1,1)`. In total, the re-audit exercised 12 independent
draw grids and 16 adversarial records.

## Test evidence

The focused suite passed **10/10 tests** under both Python 3.10.16 and Python
3.12.13: seven unit, one exhaustive property, and two integration tests. The
property test covers **252** random graph draws. The primary agent separately
ran the complete repository suite: **142/142 tests** passed under both Python
versions, and both bytecode compilation checks passed.

## Final verdict

**PASS - eligible for the verified matched random parent-graph ensemble
milestone.** The initial fail-open metadata defect is closed.

## Claim boundary

This audit establishes deterministic generation, provenance, connectedness,
and exact structural matching. It does not establish service-reliability
effects or interchangeability with alternative BA initializations, ordinary
independent-edge `G(n,p)`, or Bernoulli `p_in/p_out` SBM implementations. The
project model is explicitly fixed-edge ER and microcanonical fixed-count SBM.
