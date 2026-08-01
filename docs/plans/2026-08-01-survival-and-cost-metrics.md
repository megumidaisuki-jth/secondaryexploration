# Survival, paired-estimand, and cost-metric contract

## Scope

This slice turns validated simulation records into estimands without producing
formal scientific claims.  It implements exact administrative-censoring
semantics, within-block paired contrasts, and component-wise cost witnesses.
No p-value, stopping rule, bootstrap interval, or confirmatory multiplicity
decision is introduced in this slice.

## Discrete request-clock survival

An `EventObservation` is interpreted on the integer request clock.  At event
time `t`, the Kaplan-Meier survival value is `P(tau > t)` after processing all
events at `t`; observations censored at `t` remain in the risk set for events
at `t` and then leave without changing survival.

The restricted mean through integer horizon `H` is

`sum_{t=0}^{H-1} S(t) = E[min(tau, H)]`.

With a common pure administrative horizon, this estimand also equals the
sample mean of the directly observed restricted times `min(tau, H)`.  Under
general earlier censoring it remains a Kaplan-Meier estimand and must not be
replaced by the raw mean of observed event/censoring times.

This convention handles `tau_dep=0` exactly and gives restricted time one to
an event first observed at request one.  A quantile is the smallest event time
at which `1-S(t)` reaches the requested probability.  If censoring prevents
the curve from reaching that probability, the quantile is `None`; the horizon
is never substituted for an unobserved event.

All survival probabilities and RMST values use `fractions.Fraction`.

## Paired block summaries

For a common administrative horizon, every variant exposes:

- restricted `tau_nopath`, equal to the observed event time or censoring time;
- normalized restricted `tau_nopath`, divided by the common horizon when the
  horizon is positive;
- the fixed-horizon failure indicator;
- exact success rate and accepted value; and
- the manifest variant and block identifiers.

A within-block contrast is always `treatment - reference` and rejects results
from different manifests, missing variants, or unequal horizons.  Restricted
time differences remain observable under common administrative censoring;
raw uncensored event-time differences are not imputed.

## Component-wise cost witness

Static topology/state costs are reported separately:

- total locked capital;
- hyperedge count and incidence count;
- maximum arity and pairwise-member exposure.

Dynamic accepted-route costs report:

- accepted request count and value;
- traversed hyperedge count;
- signaled participant slots, `sum |e|` over traversed hyperedges;
- unique participants signaled within each route, summed over accepted routes;
- quadratic coordination exposure, `sum |e|^2`; and
- a canonical traversal-count histogram by hyperedge arity.

The arity histogram is the primary auditable witness.  It permits later
calculation of `|e| log |e|` or other registered sensitivity weights without
embedding a volatile floating-point scalar in the core record.  No weighted
total combines reliability and cost.

## Verification

Tests use hand-calculated event/censor tables including events and censoring at
the same time, `tau_dep=0`, non-estimable quantiles, and RMST identities.  They
also verify paired sign conventions, reject cross-manifest contrasts, and
recompute all cost fields independently from small exact route records.
