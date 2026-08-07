# Synthetic pipeline pilot v1

This directory contains the compact, tracked evidence extracted from the six
strictly validated pilot block artifacts. The multi-megabyte block artifacts
remain under the ignored `outputs/` tree; `evidence.json` binds every source
artifact and result by SHA-256 fingerprint.

## Frozen provenance

- Manifest fingerprint: `ffcdffe43e3d77b978e4a64cc2aaa368c302fe63cce92f4e6f16ad415625fb4c`
- Seed-ledger fingerprint: `284928d1a3f4679ac373f45984fb006622d88e085f0be95cb418fcf7a599988d`
- Runner revision: `618c93dea95d6a5767241f6b06fb6efd34ac1241`
- Run-summary fingerprint: `516edfeba09e12e9b6c576ae7efd7b453cfbcac65b5aa21f8325095fd4d5ac79`
- Evidence fingerprint: `bbb7f921d45a9ac0307d0a6e5205dca0f3baa1d9e12c816ccba960ba3b2d1076`
- Runtime: CPython 3.12.13 on AMD64 Windows

Rebuild the tracked evidence from the local validated artifacts with:

```powershell
C:\Users\jiate\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe `
  -m secondaryexploration.analysis.pilot `
  configs\pilot\synthetic-pipeline-v1.json `
  --workspace-root . `
  --output results\pilot\synthetic-pipeline-v1\evidence.json
```

## Descriptive result

The analysis first averages an incidence-bracketing pair of binary references
within a trace, then averages traces within a parent graph, and only then gives
parent graphs equal weight. It never treats the seven held-out traffic traces
as independent topology replicates.

Across all four registered hypergraph panels, the parent-equal global summaries
were:

| Size | Hypergraph event risk | Matched-binary event risk | Restricted normalized `tau_nopath` difference | Success-rate difference |
|---:|---:|---:|---:|---:|
| 30 | 0 | 25/84 (0.2976) | 79/672 (0.1176) | 3/560 (0.00536) |
| 60 | 0 | 2/7 (0.2857) | 5/32 (0.1563) | 31/5040 (0.00615) |

Every one of the 168 hypergraph panel-trace observations completed the horizon
without a `tau_nopath` event and had success rate 1. This is favorable pilot
evidence, but the finite lower quantile of hypergraph `tau_nopath` is not
identified: all observations are right-censored at the registered horizon.

Reliability also has a clear coordination-cost trade-off. Relative to the
matched binary panels, the global mean number of signaled participant slots per
accepted request increased by about 2.78 at size 30 and 3.64 at size 60; the
quadratic coordination exposure increased by about 38.30 and 53.23,
respectively. `evidence.json` reports all cost components separately and does
not collapse them into a weighted score.

## Demand-aware diagnostic

The demand-aware search changed the FHS5 seed topology in only one of six
blocks (`n0030-r0000-er_gnm`): there was one feasible evaluation and one
accepted step across 720 considered proposals. Its reported `tau_nopath`,
success-rate, and accepted-value summaries were identical to FHS5 in this
pilot; `tau_dep` and dynamic costs were not identical. Consequently, the current pilot does not
support a demand-aware improvement claim. A broader search-neighbourhood or
budget study must be separately registered before the formal design is frozen;
the present outputs must not be rewritten retrospectively.

## Interpretation boundary

There is only one parent replicate for each model and size (three parent-graph
instances per size). These results determine formal precision planning and
sensitivity design only. They contain no confirmatory interval, hypothesis
test, or publication-level superiority claim and cannot be relabelled as a
formal run.
