# Derived manuscript display package

This implements the frozen 2026-08-11 reporting contract, not a new analysis.
The question is whether every registered resource-matched synthetic service
contrast reproduces across the two separately analysed phases. No empirical
Lightning claim, mechanism claim, phase pooling, or additional simulation is
introduced.

## Figure contract

- Backend: Python / matplotlib, following the saved Python preference.
- Figure 1: result-free evidence-flow schematic; independent parent strata,
  within-parent paired traffic, resource-matched comparisons, separate phases,
  and complete evidence reporting. No numerical effect is encoded.
- Figure 2: two-panel point-and-interval plot; all eight global contrasts,
  both phases, exact-source estimates and multiplicity-adjusted percentile
  interval bounds. Zero and the beneficial direction are explicit.
- Figure 3: 8 by 5 categorical matrix, all 40 contrasts. Fill encodes only
  replication state; paired F/C letters encode interval direction. A hatch
  marks a closed secondary gate. No significance stars or omitted states.
- Table 1: all eight global rows, both estimates/bounds/directions, n and
  stratum counts, and replication state. JSON and Markdown are derived views.
- Full registries: 80 phase rows and 40 cross-phase rows with exact fractions,
  JSON pointers, and unchanged canonical lexicographic contrast order. Matrix
  columns follow that same order: demand-aware, fhs3, fhs5, global, nch.
- Physical width: 183 mm; editable SVG/PDF and 300 dpi PNG previews. Sans-serif
  7 pt text; lowercase bold panel letters. This is a manuscript draft package,
  not certification against current TNSM submission specifications.

## Integrity and QA

Before plotting, bind the archived Source Data byte hash and content
fingerprint, reproduce its export from fixed evidence paths, validate evidence
structure/fingerprints, and check five replay receipt hashes and byte counts.
Recompute interval directions, phase success and replication states using
exact fractions; rounding only affects displayed values. Source Data and raw
blocks remain unchanged. These reporting checks are not a new independent
implementation audit or a fresh raw-data replay.

The final package includes captions, complete numerical registries, output
hashes and QA notes. Run regression tests and the figure-source preflight;
inspect the rendered previews before committing. All synthetic conclusions
remain confined to registered designs and traffic conditions.
