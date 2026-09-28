# Display package QA

Validation performed for the generated package on 2026-09-28.

## Data integrity

- Canonical Source Data bytes match SHA-256
  `50fd83d81d54cfaf7198b3307f10a51d4a1f555b94ab06975e2d3b0b3d8e30f4`.
- Canonical content fingerprint matches
  `d82d90b43938efead325d1d2773f064b32e557d6776f3851c2cb7d37b0e5857d`.
- Recreated export equals archived Source Data. Both phase evidence structures,
  both descriptive projections and cross-phase evidence pass their existing
  structural validators. Summary/evidence fingerprints bind consistently.
- Five archived replay success receipts have matching stage identity,
  exit code zero, output byte count and SHA-256. These are provenance checks,
  not proof of an independent algorithm implementation or a new blind audit.
- All 80 phase intervals and all 40 replication records pass exact-arithmetic
  direction, gate and state checks. Each has n=60 and the registered 20+20+20
  strata. The eight global table rows agree with the complete registry.
- Every one of the 120 numerical-registry JSON pointers resolves to the
  corresponding canonical source record. Bootstrap arrays remain in Source
  Data and are not copied to the compact display registry.
- No registered contrast is dropped or reordered. Figure 2 and Table 1 use
  the eight global contrasts stipulated before results; Figure 3 retains all
  40 contrasts. Full descriptive records remain available in Source Data.
- Three-place display rounding uses exact rational arithmetic, ties to even.
  Rounded zero is `0.000`. No rounded value determines a direction or a gate.
- Git attributes preserve byte-bound input/output files and the generator's
  LF line endings across Windows checkouts. The Formal run-summary file was
  previously present in Source Data but absent at its original tracked path;
  this package also archives that existing 78,555-byte file, without regenerating
  or altering it, so the fixed-path reporting command works after checkout.

## Tests and exports

`python -m unittest tests.test_results_displays -v`: **13 tests passed**.
Tests cover missing/reordered rows, false states/directions/gates, wrong n,
all four replication states, propagation of closed global gates, exact
rounding, zero boundaries, and malformed fractions. Test fixtures are isolated
from the manuscript inputs.

`python -m tools.verify_results_displays`: **passed**. All 13 generated files
listed in manifest.json match their saved byte counts and SHA-256 hashes.
The generator hash also matches. Documentation and this QA note are tracked
by Git rather than included in the generated-output hash manifest.

| Export | Width | Height | Editable SVG text nodes | Selectable PDF characters |
|---|---:|---:|---:|---:|
| Figure 1 | 183 mm | 77 mm | 20 | 609 |
| Figure 2 | 183 mm | 82 mm | 30 | 302 |
| Figure 3 | 183 mm | 115 mm | 60 | 925 |

PNG dimensions match 300 dpi at the specified physical size. PDF dimensions
were measured from page boxes; SVG dimensions were measured from its root
attributes. PDF text extraction succeeds, and SVG text is not outlined.
All three PNG previews were visually inspected for clipping, label overlap,
readability, zero references, phase identification and matrix completeness.
The Figure 1 protocol branch was revised to make clear that both phases share
the same registered protocol, and the revised preview was inspected again.
No images were cropped, selectively adjusted, composited or AI-generated.
Figures were drawn and exported entirely with Python/matplotlib.

## Figure-source preflight

The scientific-figure source preflight reports **11 PASS, 3 WARN, 0 FAIL**.
Warnings reviewed:

1. No TIFF: deliberate for these all-vector line-art figures; SVG/PDF are the
   editable masters. PNG is only a review preview.
2. Raster DPI 300 rather than 600: acceptable for review previews; vector
   masters have no raster resolution limit. Final journal raster requests
   should be satisfied by exporting again from the saved plotting script.
3. Width reported as 4648.2 mm: the static scanner misreads the expression
   `183/25.4` as an inch value of 183. Actual SVG/PDF page widths were verified
   as 183 mm; no tight bounding-box crop changes the physical page size.

## Claim and publication boundaries

All 40 current records have the frozen `independently_confirmed` classification.
That label concerns the two experimental phases and their gate/interval rules;
it does not certify implementation independence, causality, live-network
performance, or broader external validity. The two studywise 95% families
remain separate. No p value, equivalence claim or family-to-family comparison
has been introduced.

This is a verified draft display package, not a typeset or submission-certified
paper. Current TNSM author specifications, template integration, grayscale
proofing in the final manuscript and the frozen page budget still need final
pre-submission review. The remaining coverage, sensitivity, descriptive and
runtime evidence must be represented when the Results section is written.
