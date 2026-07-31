# Secondary Exploration

Research repository for the second paper in the hypergraph payment-network
program.

**Working title**

> From Liquidity Depletion to Path Unavailability: Service-Reliability-Aware
> Topology Design for Hypergraph Payment Networks

The project is deliberately isolated from the first-paper repository. The
first-paper workspace may be consulted as a read-only source, but all new code,
experiment manifests, results, and manuscript material for paper 2 belong
here.

The authoritative approved-design draft is:

- [Paper 2 research and system design](docs/superpowers/specs/2026-07-31-secondaryexploration-design.md)
- [First implementation slice](docs/superpowers/plans/2026-07-31-project-scaffold-config-rng.md)
- [Hypergraph state-engine contract](docs/plans/2026-07-31-hypergraph-state-engine.md)
- [Full feasible-router contract](docs/plans/2026-07-31-full-feasible-router.md)

## Current implementation status

The repository currently provides the reproducibility foundation, an
immutable hypergraph balance/state engine, and complete balance-aware feasible
path search with exact tie-breaking. No topology generator, request-clock
simulator, stopping-event metric, or scientific result has been implemented
yet.

The package supports Python 3.10 or later and has no third-party runtime or
test dependency. Run the complete test suite from the repository root with:

```powershell
python -m unittest discover -s tests -v
```

## Reproducibility contract

The tracked smoke configuration is
[`configs/pilot/scaffold-smoke.json`](configs/pilot/scaffold-smoke.json). The
loader rejects missing or unknown fields, duplicate JSON keys, unsafe output
paths, invalid numeric ranges, and non-UTF-8 input. Its fingerprint is the
SHA-256 digest of canonical JSON, so a scientifically relevant configuration
change creates a different experiment identity.

Stochastic components derive independent 64-bit seeds from the tuple
`(base_seed, namespace, index)` using the versioned SHA-256 framing rule in
`secondaryexploration/randomness.py`. Reusing the same tuple replays the same
standard-library random sequence; components must use distinct semantic
namespaces such as `topology` and `traffic`.
