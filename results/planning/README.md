# Frozen planning artifacts

`formal-precision-v1.json` is the immutable recommended-A precision decision
derived from the independently audited 18-block calibration evidence. Its
fingerprint is
`c2083ff1762ec7407412e702f99bf2c58ef244e4702accc90553112fb876a2d1`.

The artifact freezes:

- parent graphs as the independent unit and traffic traces as nested
  measurements;
- equal weighting of ER-GNM, Barabasi-Albert and fixed-count SBM strata;
- two primary endpoints, eight local hierarchies and 40 confirmatory
  intervals under 95% studywise family control;
- SESOI 0.10, global half-width 0.05 and family-secondary half-width 0.10;
- 20,000 bootstrap resamples and tail probability 1/1600; and
- 20 formal plus 20 independent-confirmation parents per model and node size.

The endpoint horizon remains 12 requests per node. Formal, confirmation and
bootstrap root seeds are distinct and frozen in the artifact.

The planned count is based on preliminary variance from three calibration
parents per exact model-size cell. It is a planning choice, not achieved power
or a confirmatory result. The normal approximation chooses simulation count;
formal analysis remains the stratified parent bootstrap.

Rebuild:

```powershell
python -m secondaryexploration.analysis.precision `
  results\pilot\synthetic-calibration-v1\evidence.json `
  --workspace-root . `
  --output results\planning\formal-precision-v1.json
```

Formal execution remains gated on a verified size-120/240 performance and
parallel-resource envelope.
