# Independent audit: paired experiment runner

Date: 2026-08-01

Scope: `secondaryexploration/experiments/paired.py`, the per-request RNG entry
point in `secondaryexploration/simulation/core.py`, the paired-run plan, and
the focused unit and integration tests.

The auditor was not the implementer and performed a read-only review.  No
files were changed by the audit.

## Initial finding

The first review returned **FAIL** with one paper-level documentation blocker.
The interval-refinement formulas were correct, but the plan incorrectly
promoted an ideal infinite-random-bit property to an unconditional property of
the executable 64-bit-root deterministic family.

Because the executable family has at most `2**64` possible streams, it cannot
provide literal full route support for a tie count greater than `2**64`.  Over
the uniform domain of all 64-bit leading tickets, three bins cannot receive
identical counts; the audited maximum absolute probability discrepancy and
total variation distance are both

`2 / (3 * 2**64) = 3.6140072416e-20`.

The implementation plan, authoritative design, README, and code docstring were
revised to distinguish computational pseudorandomness from exact uniformity in
the ideal independent infinite-bit model.  The numerical three-bin statement
was limited explicitly to the uniform leading-ticket domain and was not
attributed to the root-seed-to-ticket derivation as though it were a proven
bijection.

## Independent checks

- 36 independently derived leading-ticket checks;
- 396 independently calculated route-bin mapping cells, including 180 cells
  requiring extension blocks;
- 6 deliberately constructed finite-prefix boundary cells;
- a cross-topology tie/no-tie example in which request 1 consumes one random
  choice in one topology and none in the other, while request 2 still uses the
  same indexed quantile and selects the same route;
- 11 adversarial manifest constructions, all rejected;
- 7 scientifically relevant manifest changes, all changing the fingerprint;
- a forged result using the wrong common ticket but another optimal feasible
  route, correctly rejected by `PairedRunResult`; and
- exact review of the lower/upper interval formulas
  `floor(prefix*m/2**k)` and
  `floor(((prefix+1)*m-1)/2**k)`.

## Test replay

The focused command was run on Python 3.10.16 and bundled Python 3.12.13:

```powershell
python -m unittest tests.unit.experiments.test_paired tests.integration.test_paired_experiment_runner tests.unit.simulation.test_core -v
```

Both runtimes passed 29 of 29 focused tests.

## Final decision

**PASS.** No blocking findings remain.  The executable behavior and the
revised finite-seed claim boundary are consistent.
