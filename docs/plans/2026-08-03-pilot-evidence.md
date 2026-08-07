# Parent-aware pilot evidence contract

## Scope

Convert a complete synthetic pilot run into a small tracked evidence artifact
without committing the multi-megabyte block witnesses and without promoting
pilot descriptions to confirmatory inference.

## Trust chain

1. Strictly load the run summary and reject duplicate keys, non-finite JSON,
   unknown fields, malformed block records, inconsistent totals, or a bad
   summary fingerprint.
2. Bind the summary to the registered manifest, semantic seed ledger, code
   revision, and runtime environment.
3. Load every canonical `blocks/<block-key>.json` path beneath the summary
   directory and apply the full block-artifact scientific-context validator.
4. Rebuild the run summary from the loaded blocks and require exact equality.
5. Generate `evidence.json` deterministically and bind it to every block and
   result fingerprint plus the run-summary fingerprint.

## Pairing and aggregation

Each observation is a registered hypergraph panel on one held-out trace. When
an odd incidence budget has two adjacent matched-binary references, average the
two binary outcomes within that trace before forming the contrast. Average
trace contrasts within each parent graph. Give independent parent graphs equal
weight only after that first aggregation. Never count traffic regimes as
independent topology replicates.

The global descriptive contrast gives each of the four registered hypergraph
panels equal weight within the same hierarchy. Size 30 and size 60 remain
separate analysis cells. Same-distribution and shifted traffic are also
reported separately.

## Censoring and metrics

For `tau_nopath`, retain both:

- the restricted request time divided by the common horizon; and
- the fixed-horizon event indicator.

Thus a censored run contributes follow-up through the horizon without being
misrepresented as an observed failure at the horizon. The compact artifact
does not estimate a finite censored quantile from the present one-replicate
pilot.

Success rate and accepted value are reported alongside reliability. Static and
dynamic costs are component-wise. Dynamic counts are normalized both per
offered request and, where defined, per accepted request. No weighted total
score is introduced.

## Output policy

Track only the deterministic compact evidence and its human-readable summary.
Keep complete simulation witnesses under ignored `outputs/`; their exact
fingerprints and the regeneration command remain in the tracked result. Remove
transient stdout/stderr capture after completion because the validated run
summary supersedes them.

## Interpretation gate

The pilot can set precision targets, horizons, search sensitivities, and formal
sample sizes. It cannot supply confirmatory intervals or claims. In particular,
right censoring at the pilot horizon and an inactive demand-aware search must
be resolved by a separately registered extension rather than by editing the
completed pilot manifest or outputs.
