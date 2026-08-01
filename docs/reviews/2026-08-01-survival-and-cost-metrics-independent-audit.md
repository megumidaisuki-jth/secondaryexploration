# Independent audit: survival and cost metrics

Date: 2026-08-01

Scope: `secondaryexploration/metrics/`, the survival-and-cost plan, and the
focused metric tests.  The auditor was not the implementer and changed no
files.

## Independent checks

- 160 random small survival samples using an independently implemented risk
  set and survival calculation;
- exact same-time ordering in which events use the risk set before censoring
  exits;
- survival values, fixed-horizon failure risk, four quantile levels, and
  discrete RMST;
- `tau=0`, all-event, all-censored, same-time event/censor, identified
  zero-survival tails, and rejected nonzero-tail extrapolation;
- 120 additional pure-administrative-censoring samples satisfying
  `RMST(H) = sum_{t=0}^{H-1} S(t) = mean(min(tau,H))`;
- 24 small runs mixing binary, ternary, and four-member hyperedges, with every
  static and dynamic cost field recomputed independently;
- 112 accepted and 176 rejected requests, confirming that rejection creates
  no dynamic route cost;
- 12 paired blocks, including raw and normalized restricted `tau_nopath`,
  treatment-minus-reference signs, explicit failure status, and empty traces;
  and
- 18 adversarial inputs covering forged KM points/order, invalid samples,
  probabilities and evaluation times, invalid extrapolation, variant and
  manifest mismatches, equal contrast arms, and invalid cost sources.

The auditor suggested clarifying that the direct restricted-time sample-mean
identity requires common pure administrative censoring; under earlier general
censoring, RMST is a Kaplan-Meier estimand.  The plan now states this boundary.
The suggested explicit empty-trace normalized-contrast test was also added.

## Test replay

```powershell
python -m unittest discover -s tests/unit/metrics -p 'test_*.py'
```

Python 3.10.16 and bundled Python 3.12.13 each passed 13 of 13 focused tests
at audit time.

## Decision

**PASS.** No blocking issue was found.
