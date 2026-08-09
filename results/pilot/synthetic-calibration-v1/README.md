# Synthetic calibration pilot v1

This directory contains compact, replay-validated planning evidence from the
complete 18-block calibration pilot. It is not formal evidence and cannot be
used for confirmatory superiority claims.

## Provenance

- Frozen manifest fingerprint:
  `cd15e32990c65b8737105f660e592525b2fc347ff7a51f2eb991e02ac023da89`
- Seed-ledger fingerprint:
  `fd045f93429e068ad19e2e3db35397dfbbfa8fa1ee272a2fd7cabd22cc16fe1c`
- Runner revision: `f9b77c7fb9093352826b28a5588f7b490b993c46`
- Evidence-analysis revision: `8179e856182056642536cfbeb0ca3a452c2bc54f`
- Complete run-summary fingerprint:
  `6ab7a16cb122a4df6be2b05c211c9086c8039f63c229d40d23353fc85f4012fc`
- Calibration evidence fingerprint:
  `7c5c8bc98939b5b9f3fa602b3b3f3986fd531004c06b1cb8277d6b52d653c0ff`
- Runtime: CPython 3.12.13 on AMD64 Windows

The compact `evidence.json` binds all 18 ignored block witnesses and their
full replay results. It contains 504 trace-level paired contrasts, aggregated
first into 144 parent cells and then into 48 exact
size/model/family/traffic-scope dispersion cells. Each dispersion cell has
three independent parent graphs; traffic regimes and requests are nested
measurements, not additional `n`.

## Censoring decision

The 12-request-per-node horizon did not make the registered lower
`tau_nopath` quantile broadly identifiable. Only 2 of 48 cells passed the
strict gate requiring all three parents, the source topology, and every
matched-binary arm to identify the quantile. The two passing cells were both
FHS-3 on size-60 fixed-count SBM parents (same-distribution and shifted
traffic).

Across all models and traffic scopes, observed source `tau_nopath` event
coverage was:

| Size | Demand-aware | FHS-3 | FHS-5 | NCH |
|---:|---:|---:|---:|---:|
| 30 | 3/63 | 4/63 | 1/63 | 0/63 |
| 60 | 3/63 | 11/63 | 3/63 | 0/63 |

Accordingly, the frozen formal route should make restricted time/RMST and
fixed-horizon failure risk primary. The lower quantile remains explicitly
censored or exploratory; a censored horizon is never imputed as a failure
time.

## Demand-aware coverage

With the training-only proposal budget increased from 120 to 5,000,
demand-aware search changed its FHS-5 seed topology in 8 of 18 parent graphs.
There were 226 feasible evaluations and 8 accepted steps. This resolves the
first pilot's near-inactive-search diagnostic without using held-out outcomes
to tune the proposal budget.

## Runtime envelope

The complete calibration consumed 3.43 hours of recorded generation plus
exact replay-validation time. Median total time per block and the preregistered
repeat-ratio projections are:

| Model | n=30 observed | n=60 observed | n=120 projected | n=240 projected |
|---|---:|---:|---:|---:|
| Barabasi-Albert | 4.20 min | 20.08 min | 1.60 h | 7.64 h |
| ER-GNM | 3.95 min | 17.08 min | 1.23 h | 5.32 h |
| Fixed-count SBM | 4.18 min | 18.99 min | 1.44 h | 6.52 h |

The projections repeat each model's observed 30-to-60 median-time ratio. They
are conservative planning extrapolations, not benchmark guarantees. A formal
design with many independent size-240 parents is computationally infeasible
without a separately verified optimization or a declared compute allocation.

## Precision freeze still required

The calibration estimates preliminary parent-level dispersion but does not
invent the smallest effect of scientific interest, simultaneous interval
half-width, confidence family, bootstrap resample count, or formal number of
parents. Those values must be frozen in a separate precision artifact before
formal runs begin. Three calibration parents per exact model-size cell are not
a powered formal sample size.

## Rebuild

```powershell
python -m secondaryexploration.analysis.calibration `
  configs\pilot\synthetic-calibration-v1.json `
  --workspace-root . `
  --output results\pilot\synthetic-calibration-v1\evidence.json
```

The writer rejects an in-progress run, a modified calibration manifest, any
missing/extra block, malformed JSON, or a failed source replay before writing
the compact artifact atomically.
