# Study Manifest and Parent-Block Pipeline Independent Audit

**Date:** 2026-08-03

**Verdict:** PASS after two blocking findings were fixed

## Scope

The audit independently attacked the strict study manifest, phase-separated
seed ledger, matched synthetic parent inputs, declared traffic regimes,
train-once topology/capacity pipeline, binary resource panels, cost-only clique
references, paired held-out execution, result fingerprint, and complete replay.

## Blocking findings and resolutions

1. The initial parent-block fingerprint omitted individual demand-aware score
   fields and did not bind clique-reference nodes or prove that each reference
   was the exact clique expansion of one source. The implementation now hashes
   the complete score, binds clique nodes, requires one canonical reference per
   source, and verifies exact expansion equality. Adversarial score and isolated
   node mutations now change identity or fail construction and replay.
2. `maximum_parent_attempts` initially inherited the manifest's generic
   1,000,000 ceiling while the parent generator supports at most 10,000. The
   manifest now enforces `[1, 10000]`; independent Python 3.10 and 3.12 checks
   accept 10,000 and reject 10,001 before execution.

## Independent evidence

- Unknown, missing, duplicate, non-finite, malformed nested, and invalid UTF-8
  JSON inputs were rejected. Pilot provenance must be null; valid formal and
  confirmation shapes require all four primary sizes, multiple parents, and
  bound basis, code, and environment identities.
- The frozen manifest and ledger identities are respectively
  `ffcdffe43e3d77b978e4a64cc2aaa368c302fe63cce92f4e6f16ad415625fb4c`
  and
  `284928d1a3f4679ac373f45984fb006622d88e085f0be95cb418fcf7a599988d`.
  Canonical bytes match across Python 3.10 and 3.12.
- Independent n=30 and n=60 ER, BA, and fixed-count SBM generation recovered
  exact shared edge counts 81 and 171; SBM within-edge counts were 60 and 128.
  Every graph was connected and replayable.
- The registry contains exactly four training kernels, four
  same-distribution tests, and the declared hotspot-relocation,
  direction-reversal, and cross-community shifts. Traffic construction uses
  only canonical node indices and registered parameters.
- Every finite parent, capacity, binary-matching, traffic, and routing seed was
  unique. Expanding sizes, parents, or trace counts preserved all earlier
  semantic seeds, and forged ledgers failed complete regeneration.
- In an independent held-out leakage attack, changing only the held-out
  community cross weight from 6 to 7 left parent seeds, training seeds, request
  traces, aggregate demand, demand-aware output, and every trained capacity
  state identical. Only held-out runs and the enclosing block identity changed.
- A representative block contained four hypergraph sources, four resource
  panels, six deduplicated binary matches, and ten total service variants.
  Every actual incidence delta matched its declared 0 or -1/+1 relation. The
  four exact clique expansions remained cost references and never entered
  service simulation.
- All variants shared one capacity manifest and plan and exhausted the same
  evaluation budget. All seven held-out regimes ran with the exact ledger
  traffic and routing roots, common request objects, and request-indexed route
  tickets.
- The final versioned fingerprint binds complete parent, seed, training,
  topology, capacity, panel, clique, route, state, and event-time records.
  Exact replay passed; score and record mutations were rejected.
- On the frozen audited tree, Python 3.10 and 3.12 each passed 267/267 tests;
  `compileall` and `git diff --check` passed. A minimal n=30 audit block required
  about 11.7 seconds, while generation plus exact replay and tamper replay took
  about 35.1 seconds on the audit host.

## Non-blocking residual risks

Formal and confirmation manifests and n=120/n=240 wall-clock measurements are
not yet frozen. Complete replay will be expensive at formal scale. Basis,
code-revision, and environment digests are schema-bound, but a later freeze
workflow must verify that the referenced artifacts exist. That workflow should
also record the precision rationale used to select parent and trace counts.
