# Synthetic experiment manuscript displays

Draft reporting package derived from the complete, archived phase evidence.
No simulation or bootstrap was rerun to make these displays.

## Contents

- [Figure 1: design and evidence flow](figure-1-design.png)
- [Figure 2: all eight global contrasts](figure-2-global-contrasts.png)
- [Figure 3: all 40 replication states](figure-3-replication-matrix.png)
- [Table 1: global numerical results](table-1.md)
- [Figure captions and statistical definitions](captions.md)
- [Complete numerical registry](numerical-registry.json): 80 phase rows and
  40 cross-phase rows; exact fractions, three-decimal display values, gates,
  directions, sample counts and JSON source pointers.
- [Table 1 machine-readable version](table-1.json)
- [Output hashes and generation environment](manifest.json)
- [QA record and limitations](QA.md)

Each figure also has an editable SVG and a vector PDF with the same basename.
PNG files are 300 dpi review previews, not the submission line-art originals.
Canonical fractions, bootstrap arrays, parent values, all descriptive metrics,
coverage and sensitivity records remain in the complete
[Source Data](../../../results/source-data/synthetic-hypergraph-payment-v1/source-data.json).
The compact numerical registry deliberately references rather than duplicates
bootstrap arrays; it does not replace Source Data.

## Reproduction

From the repository root with Python and matplotlib installed:

```powershell
python -m unittest tests.test_results_displays -v
python -m tools.build_results_displays --check-only
python -m tools.build_results_displays
python -m tools.verify_results_displays
```

The generator checks the fixed archived Source Data SHA-256, reproduces its
export from the evidence files, validates evidence structures and fingerprints,
and checks all five archived replay receipt byte counts and hashes. It then
recomputes reporting directions, gates and replication classifications using
exact fractions. It does not read raw blocks or launch long-running analysis.
The generated files in this directory are reproducible derived outputs; a
rerun replaces them, not the underlying evidence or simulation data.
The export verifier additionally uses Pillow and pypdf to inspect dimensions,
selectable text and source pointers; it does not render or modify the figures.

## Interpretation boundary

All 40 registered contrasts have the evidence state `independently_confirmed`:
beneficial adjusted intervals and applicable open gates in both phases.
This is the frozen cross-phase classification, not an assertion of independent
code implementation, a causal mechanism, or performance on live payment
networks. The analysis is limited to the registered synthetic benchmark.
Eight global rows and all 32 named-family rows are retained regardless of state.

The two phases' 95% families remain separate; this package makes no simultaneous
95% guarantee over the combined 80 contrasts. Named source families are compared
against their own resource-matched binary references, not against each other.
The next writing step must include the remaining descriptive/coverage/runtime
evidence and limitations from Source Data, not only the main figures.

Final TNSM template layout, current submission specifications and page-budget
validation are still pending. This package is not a completed manuscript.
