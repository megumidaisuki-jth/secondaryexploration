# Parent-level hierarchical inference contract

## Independent unit and estimand

The independent sampling unit is the parent-graph instance.  A request trace
is a repeated measurement within that parent, not an independent topology
replicate.

For one registered contrast and metric:

1. compute `treatment - reference` within every paired trace block;
2. average those trace-level contrasts within each parent graph; and
3. average the parent-graph means with equal weight.

Parents with more simulated traffic traces therefore do not receive more
inferential weight. Every observation declares a registered analysis-cell ID
(for example graph family, size, resource panel, and traffic regime); one
sample cannot mix cells implicitly. Parent identifiers and trace identifiers
are explicit, canonical, and unique. Manifest fingerprints must also be unique
within the sample, so one trace cannot be counted twice under renamed
identifiers. A contrast sample rejects mixed analysis cells,
treatment/reference labels, metrics or observation horizons, duplicate
traces, duplicate parents, missing aligned parents, and noncanonical order.

The first implemented metrics are normalized restricted `tau_nopath`,
fixed-horizon failure risk, success rate, and accepted value.  Undefined
empty-horizon quantities cannot enter an inferential sample.

## Cluster bootstrap

The nonparametric cluster bootstrap resamples parent-graph means with
replacement.  It never resamples trace blocks as independent observations.
Bootstrap replicate `b` uses a separately derived seed in namespace
`statistics.parent_bootstrap`, so increasing the registered replicate count
does not alter earlier resamples.

Every contrast in a simultaneous family must contain the same canonical
parent identifiers, analysis cell, horizon, and parent-trace-manifest layout.
A replicate uses the same resampled parent indices for all contrasts,
preserving their cross-contrast dependence. Missing trace blocks therefore
fail closed instead of silently changing one contrast's parent means.

The point estimate and bootstrap values are exact `Fraction` objects.
Percentile endpoints use the left empirical quantile, the smallest value whose
empirical CDF reaches the requested probability.
The registered replicate count must place at least one empirical order
statistic in every adjusted tail (`B * alpha/(2K) >= 1`); otherwise interval
construction fails rather than presenting unresolved tails as precise.

## Simultaneous intervals

For `K` registered confirmatory contrasts and familywise level `1-alpha`, each
two-sided percentile interval uses tails `alpha/(2K)`.  This is a transparent
Bonferroni adjustment applied to parent-cluster bootstrap distributions.  The
union-bound logic controls multiplicity conditional on valid marginal
bootstrap coverage; the resulting intervals are asymptotic bootstrap
approximations, not finite-sample exact confidence sets.

Exploratory contrasts reuse the same aligned parent resamples to aid
comparison but receive nominal tails `alpha/2`; they are not included in `K`
and cannot make the confirmatory family artificially more conservative.

The bootstrap root seed, replicate count, confidence level, ordered contrast
registrations, parent IDs, and resulting interval method are frozen in the
formal manifest before confirmatory execution.  Simulation or resampling does
not continue until an interval excludes zero.

## Confirmatory hierarchy

The executable registration has exactly one tier-1 global contrast, zero or
more tier-2 secondary contrasts, and zero or more explicitly exploratory
contrasts.  Every registration declares whether a positive or negative
treatment-minus-reference value is beneficial.

Tier 2 is confirmatorily eligible only if the global simultaneous interval is
strictly on its registered beneficial side of zero.  Otherwise tier-2 effects
and intervals are still reported but labeled descriptive.  Exploratory
contrasts are never relabeled confirmatory.  Effect sizes and intervals are
returned regardless of gate outcome.

## Verification

Tests use exact hand-calculated unequal-trace parent examples to prove equal
parent weighting, known bootstrap index vectors, resample-prefix stability,
shared indices across contrast families, exact empirical quantiles,
Bonferroni tail probabilities, hierarchy gating in both directions, and
adversarial duplicate/misaligned/mixed records.
