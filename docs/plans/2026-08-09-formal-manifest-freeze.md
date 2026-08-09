# Formal and confirmation manifest freeze

The formal and independent-confirmation manifests are generated only from the
audited calibration manifest, audited calibration evidence, and frozen
recommended-A precision artifact. Both phases retain all four sizes, all
registered traffic regimes, 12 requests per node, the training-only
demand-aware search budget and exact resource-matching rules.

Each phase contains 20 parent replicates for every size. The runner expands
each parent replicate into ER-GNM, Barabasi-Albert and fixed-count SBM model
strata, yielding 240 blocks per phase. Formal and confirmation phases use
base seeds 2026081001 and 2026081002, respectively. Their output roots and
manifest fingerprints are distinct.

The manifests bind runner revision
`d853926b2704db4f035184997388c8b382e5b7d9` and the CPython 3.12.13 Windows
AMD64 environment fingerprint. Formal execution must provide the precision
artifact and calibration evidence again; the runner strictly replays them and
checks basis, phase seed, horizon, parent count, revision and environment
before creating the first output block.

The runner also reloads the fixed calibration manifest and reconstructs the
entire expected formal/confirmation mapping. Traffic regimes, topology and
capacity search, capital, amount weights, resource matching and every other
non-phase field must match exactly. Finally, Git proves that all
execution-relevant package sources equal the declared revision and rejects
modified or untracked execution code. The manifest-generation helper itself
is excluded from that source comparison because it is not imported by the
simulation runner.

Frozen manifest fingerprints:

- formal: `d06a5f4bb146fa56fb53408fb48db1b69e5b522e7235b826b2ddcd6a0f3b76ad`;
- confirmation: `427c9840d5fd037ae6b66d0f45d68d8188b42b2ac72702d4391c0d2b536a38c8`.

Write-free launch validation uses:

```powershell
python -m secondaryexploration.experiments.runner `
  configs\formal\synthetic-formal-v1.json `
  --workspace-root . `
  --code-revision d853926b2704db4f035184997388c8b382e5b7d9 `
  --precision results\planning\formal-precision-v1.json `
  --calibration-evidence results\pilot\synthetic-calibration-v1\evidence.json `
  --calibration-manifest configs\pilot\synthetic-calibration-v1.json `
  --preflight-only
```

The same command with the confirmation manifest validates the disjoint
confirmation phase. Preflight returns `preflight-valid-no-execution` and must
not create either output directory.
