# Independent audit: calibration-pilot freeze inputs

## Verdict

PASS. No blocking defect or uncommitted auditor change.

## Manifest comparison and randomness

An independent raw-JSON comparison against
`synthetic-pipeline-v1.json` found exactly the six registered changes:
`study_id`, `base_seed`, `output_root`, `parent_replicates`,
`requests_per_node`, and `topology_search.proposal_budget`. Every other
scientific field was exactly equal.

- Calibration manifest fingerprint:
  `cd15e32990c65b8737105f660e592525b2fc347ff7a51f2eb991e02ac023da89`.
- Calibration ledger fingerprint:
  `fd045f93429e068ad19e2e3db35397dfbbfa8fa1ee272a2fd7cabd22cc16fe1c`.
- Six parent-seed records times three graph models produce 18 blocks.
- The ledger contains 66 trace-seed records.
- All 150 actual calibration seed slots are unique and have zero intersection
  with all 50 actual seed slots in the first pilot.
- Calibration training and held-out trace/routing seed sets are disjoint.

The design text treats the three parent replicates separately inside every
model-size stratum. It does not pool ER, BA, and SBM into nine identically
distributed observations and does not treat the seven traffic traces as
independent `n`.

## Training-only search diagnostic

The auditor independently replayed the three budgets using only parent graphs,
four registered training traces per parent, the training demand matrix, and
the demand-aware topology search. It did not construct a test trace, paired
run, capacity optimization, or held-out outcome.

The six-block exact summaries were:

| Proposal budget | Changed blocks | Feasible blocks | Feasible evaluations | Accepted steps | Proposals considered |
|---:|---:|---:|---:|---:|---:|
| 120 | 1 | 1 | 1 | 1 | 720 |
| 1,000 | 3 | 3 | 24 | 3 | 6,000 |
| 5,000 | 4 | 4 | 34 | 4 | 30,000 |

The frozen diagnostic fingerprint is
`1baceb77d3f98afe9ee425f2e3b1fe9c3f111a9351abe886f5b7c96bcbf9c781`.
Source replay reproduced the tracked canonical artifact on Python 3.10 and
3.12.

The strict loader rejected duplicate JSON keys, NaN, block-level unknown
fields, and budget-result unknown fields, including attacks that recomputed
the outer fingerprint. The seed topology is derived from the manifest's
registered `demand_aware_seed_family`; unregistered arities and non-FHS
families fail closed.

## Verification

- Python 3.12 full suite: 273/273 PASS.
- Python 3.10 split suite: exact 11/11, property 8/8, unit 217/217,
  integration 13/13, and top-level 24/24 PASS (273/273 total).
- Auditor-focused source-replay and manifest suite: 10/10 PASS on both
  interpreters.
- Dual-version `compileall`: PASS.
- `git diff --check`: PASS apart from informational CRLF warnings.

## Residual trust boundary

As elsewhere in the project, unkeyed SHA-256 provides deterministic integrity,
not external source authentication. The calibration is an exploratory
variance/horizon/search-coverage study, not a powered formal sample.
