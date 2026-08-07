# Independent audit: parent-aware pilot evidence

## Verdict

PASS. No blocking defect remained after hardening, and the auditor did not
modify repository files.

## Independent reconstruction

The auditor bypassed `secondaryexploration.analysis.pilot` and recomputed the
evidence directly from all six raw block artifacts with exact `Fraction`
arithmetic:

- 24 resource panels: 11 odd-incidence panels with ordered `[-1,+1]` binary
  brackets and 13 even-incidence panels with one exact `[0]` arm;
- 168 panel-trace contrasts and 245 binary-arm observations;
- eight size-family rows, sixteen size-family-scope rows, and two global size
  rows, all exactly equal to the tracked evidence;
- size 30 global event risk `0` versus `25/84`, normalized restricted
  `tau_nopath` difference `79/672`, and success-rate difference `3/560`;
- size 60 global event risk `0` versus `2/7`, normalized restricted
  `tau_nopath` difference `5/32`, and success-rate difference `31/5040`.

All 168 hypergraph source observations were independently confirmed to be
right-censored at the registered horizon with success rate one. The evidence
therefore preserves censoring rather than recording horizon as an observed
failure.

## Provenance and aggregation attacks

The auditor independently recomputed all six artifact and result fingerprints,
the manifest fingerprint, seed-ledger fingerprint, run-summary fingerprint,
and evidence fingerprint. Python 3.10 and 3.12 regenerated canonical evidence
bytes identical to the tracked file.

The following attacks were rejected:

- run-summary bit flips and artifact mixing;
- a coordinated summary refingerprint with `../` block-path escape;
- an output target or explicit summary path outside the workspace;
- evidence mutation without refingerprinting;
- coordinated evidence refingerprinting with a nested unknown summary field;
- a forged success-rate difference inconsistent with its source and binary
  arms;
- an unknown runtime-environment field; and
- coordinated scientific-summary forgery under source-bound validation.

The odd-budget binary pair was confirmed to be averaged within each trace
before a contrast is formed. Trace contrasts were averaged within each parent
before parent-equal aggregation, and size 30 and size 60 were not mixed.

## Verification

- Python 3.10.16 full suite: 271/271 PASS.
- Python 3.12.13 full suite: 271/271 PASS.
- Auditor-focused suite on both interpreters: 4/4 PASS.
- `compileall`: PASS on both interpreters.
- `git diff --check`: PASS, apart from informational CRLF conversion warnings.

## Residual trust boundary

Standalone validation proves strict schema, internal exact arithmetic, and
content-fingerprint consistency. Scientific provenance requires the supported
source-bound path, which deterministically rebuilds evidence from the manifest,
ledger, run summary, and complete block artifacts. Unkeyed SHA-256 is an
integrity mechanism, not source authentication; an attacker able to replace all
sources and recompute every hash remains outside this repository-local trust
model.
